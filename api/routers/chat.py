from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Video
from pydantic import BaseModel
from uuid import UUID
import httpx
import os

router = APIRouter()

OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODELL = os.getenv("OLLAMA_MODELL", "llama3")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")

# Chatverlauf pro Job im Speicher (einfache Lösung)
_verlaeufe: dict = {}


class ChatNachricht(BaseModel):
    frage: str


class ChatAntwort(BaseModel):
    antwort: str
    verlauf: list


@router.post("/{job_id}", response_model=ChatAntwort)
async def chat(
    job_id: UUID,
    nachricht: ChatNachricht,
    db: AsyncSession = Depends(get_db)
):
    # Video laden
    ergebnis = await db.execute(select(Video).where(Video.job_id == job_id))
    video = ergebnis.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video nicht gefunden")
    if not video.transkript:
        raise HTTPException(400, "Kein Transkript vorhanden")

    job_key = str(job_id)
    if job_key not in _verlaeufe:
        _verlaeufe[job_key] = []

    verlauf = _verlaeufe[job_key]

    # System-Kontext aufbauen
    system = f"""Du bist ein hilfreicher Assistent für das YouTube-Video:
Titel: {video.titel}
Kanal: {video.kanal}

Hier ist das Transkript des Videos (ggf. gekürzt):
---
{video.transkript[:10000]}
---

Beantworte Fragen NUR basierend auf dem Inhalt dieses Videos.
Antworte auf Deutsch. Sei präzise und hilfreich."""

    verlauf.append({"rolle": "nutzer", "text": nachricht.frage})

    # Nachrichten für LLM formatieren
    nachrichten = [{"role": "system", "content": system}]
    for eintrag in verlauf[-10:]:  # Letzte 10 Nachrichten
        rolle = "user" if eintrag["rolle"] == "nutzer" else "assistant"
        nachrichten.append({"role": rolle, "content": eintrag["text"]})

    # LLM anfragen
    if OPENAI_KEY:
        antwort = await _openai_chat(nachrichten)
    else:
        antwort = await _ollama_chat(nachrichten)

    verlauf.append({"rolle": "assistent", "text": antwort})
    _verlaeufe[job_key] = verlauf[-20:]  # Max 20 Einträge

    return ChatAntwort(antwort=antwort, verlauf=verlauf)


@router.delete("/{job_id}/verlauf")
async def verlauf_loeschen(job_id: UUID):
    _verlaeufe.pop(str(job_id), None)
    return {"geloescht": True}


async def _ollama_chat(nachrichten: list) -> str:
    # Ollama-Format: alle Nachrichten zu einem Prompt zusammenbauen
    prompt = ""
    for m in nachrichten:
        if m["role"] == "system":
            prompt += m["content"] + "\n\n"
        elif m["role"] == "user":
            prompt += f"Nutzer: {m['content']}\n"
        else:
            prompt += f"Assistent: {m['content']}\n"
    prompt += "Assistent:"

    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":   OLLAMA_MODELL,
                    "prompt":  prompt,
                    "stream":  False,
                    "options": {"temperature": 0.7, "num_predict": 512}
                }
            )
            r.raise_for_status()
            return r.json().get("response", "Keine Antwort erhalten.")
    except Exception as e:
        return f"Fehler beim LLM: {str(e)}"


async def _openai_chat(nachrichten: list) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                json={
                    "model":       "gpt-4o-mini",
                    "messages":    nachrichten,
                    "max_tokens":  512,
                    "temperature": 0.7,
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenAI Fehler: {str(e)}"