import redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
r = redis.from_url(REDIS_URL)
WN = "yt_jobs_normal"
WP = "yt_jobs_prioritaet"


def job_einreihen(job_id, optionen, prioritaet=0):
    nutzlast = json.dumps({"job_id": str(job_id), "optionen": optionen})
    r.rpush(WP if prioritaet > 0 else WN, nutzlast)


def warteschlangen_laenge():
    return {"normal": r.llen(WN), "prioritaet": r.llen(WP)}


def fortschritt_setzen(job_id, fortschritt, status):
    r.setex(f"fortschritt:{job_id}", 3600,
            json.dumps({"fortschritt": fortschritt, "status": status}))


def fortschritt_abrufen(job_id):
    daten = r.get(f"fortschritt:{job_id}")
    return json.loads(daten) if daten else {"fortschritt": 0, "status": "warteschlange"}


# ── NEU: Abbruch-Funktionen ───────────────────────────────

def abbruch_signalisieren(job_id: str) -> None:
    """Setzt ein Abbruch-Flag in Redis das der Worker liest."""
    r.setex(f"abbruch:{job_id}", 3600, "1")


def abbruch_pruefen(job_id: str) -> bool:
    """Worker prüft ob Abbruch angefordert wurde."""
    return r.exists(f"abbruch:{job_id}") == 1


def abbruch_loeschen(job_id: str) -> None:
    """Abbruch-Flag nach Verarbeitung löschen."""
    r.delete(f"abbruch:{job_id}")


def aus_warteschlange_entfernen(job_id: str) -> bool:
    """
    Job aus Warteschlange entfernen falls noch nicht gestartet.
    Gibt True zurück wenn erfolgreich entfernt.
    """
    for schlange in [WP, WN]:
        eintraege = r.lrange(schlange, 0, -1)
        for eintrag in eintraege:
            try:
                daten = json.loads(eintrag)
                if daten.get("job_id") == str(job_id):
                    r.lrem(schlange, 1, eintrag)
                    return True
            except Exception:
                continue
    return False