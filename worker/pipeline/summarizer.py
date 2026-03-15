import httpx, os, logging
log = logging.getLogger("summarizer")
OLLAMA = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
MODELL = os.getenv("OLLAMA_MODELL", "llama3")
OAIKEY = os.getenv("OPENAI_API_KEY", "")

PROMPTS = {
    "stichpunkte": "Fasse als Stichpunkte zusammen:\n\n{t}\n\nZusammenfassung:",
    "ausfuehrlich": "Ausfuehrliche Zusammenfassung:\n\n{t}\n\nZusammenfassung:",
    "kernaussagen": "5-7 Kernaussagen:\n\n{t}\n\nKernaussagen:",
    "podcast_skript": "Als Podcast-Skript:\n\n{t}\n\nSkript:",
}


def zusammenfassung_erstellen(transkript, stil="stichpunkte", titel=""):
    if not transkript: return "Kein Transkript."
    prompt = PROMPTS.get(stil, PROMPTS["stichpunkte"]).format(t=transkript[:12000])
    if OAIKEY: return _openai(prompt)
    return _ollama(prompt)


def _ollama(prompt):
    try:
        with httpx.Client(timeout=120) as c:
            r = c.post(f"{OLLAMA}/api/generate",
                       json={"model":MODELL,"prompt":prompt,"stream":False,
                             "options":{"temperature":0.3,"num_predict":1024}})
            r.raise_for_status()
            return r.json().get("response","Fehler")
    except Exception as e:
        log.warning(f"Ollama: {e}")
        return _fallback(prompt)


def _openai(prompt):
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post("https://api.openai.com/v1/chat/completions",
                       headers={"Authorization":f"Bearer {OAIKEY}"},
                       json={"model":"gpt-4o-mini",
                             "messages":[{"role":"user","content":prompt}],
                             "max_tokens":1024,"temperature":0.3})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"OpenAI: {e}")
        return _fallback(prompt)


def _fallback(text):
    saetze = text.replace("\n"," ").split(". ")
    return "\n".join(f"* {s.strip()}" for s in saetze[::max(1,len(saetze)//8)][:8] if s.strip())
