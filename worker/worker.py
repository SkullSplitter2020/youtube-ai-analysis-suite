import redis, json, os, time, logging, subprocess
from pipeline.downloader import video_herunterladen
from pipeline.audio_processor import audio_verarbeiten
from pipeline.transcriber import audio_transkribieren
from pipeline.chapter_detector import kapitel_erkennen
from pipeline.summarizer import zusammenfassung_erstellen
from pipeline.podcast_exporter import podcast_exportieren
from db_worker import (
    db_session_erstellen,
    job_status_aktualisieren,
    video_daten_speichern
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
r = redis.from_url(REDIS_URL)
SCHLANGEN = ["yt_jobs_prioritaet", "yt_jobs_normal"]


def fortschritt(jid, p, s):
    r.setex(f"fortschritt:{jid}", 3600,
            json.dumps({"fortschritt": p, "status": s}))


def abbruch_angefordert(jid: str) -> bool:
    """Prüft ob Nutzer Abbruch angefordert hat."""
    return r.exists(f"abbruch:{jid}") == 1


def abbruch_aufraeumen(jid: str):
    """Abbruch-Flag löschen + temporäre Dateien entfernen."""
    r.delete(f"abbruch:{jid}")
    # Temporäre Audio-Dateien löschen
    audio_verz = f"/app/data/audio/{jid}"
    if os.path.exists(audio_verz):
        try:
            import shutil
            shutil.rmtree(audio_verz)
            log.info(f"Temporäre Dateien gelöscht: {audio_verz}")
        except Exception as e:
            log.warning(f"Dateien konnten nicht gelöscht werden: {e}")


class JobAbgebrochen(Exception):
    """Wird geworfen wenn der Nutzer den Job abbricht."""
    pass


def abbruch_check(jid: str, schritt: str):
    """An kritischen Stellen prüfen ob Abbruch gewünscht."""
    if abbruch_angefordert(jid):
        log.info(f"Abbruch erkannt bei Schritt '{schritt}' für Job {jid}")
        raise JobAbgebrochen(f"Abgebrochen bei: {schritt}")


def verarbeiten(jid, opt):
    log.info(f"▶ Starte Job {jid}")
    ses = db_session_erstellen()

    try:
        # ── Schritt 1: Download ───────────────────────────
        abbruch_check(jid, "vor Download")
        job_status_aktualisieren(ses, jid, "herunterladen", 5.0)
        fortschritt(jid, 5, "herunterladen")
        info, pfad = video_herunterladen(jid, opt)

        # ── Schritt 2: Audio ──────────────────────────────
        abbruch_check(jid, "vor Audio-Verarbeitung")
        job_status_aktualisieren(ses, jid, "verarbeitung", 20.0)
        fortschritt(jid, 20, "verarbeitung")
        audio = audio_verarbeiten(pfad, jid)

        # ── Schritt 3: Transkription ──────────────────────
        abbruch_check(jid, "vor Transkription")
        job_status_aktualisieren(ses, jid, "transkription", 35.0)
        fortschritt(jid, 35, "transkription")
        text, segs = audio_transkribieren(
            audio,
            opt.get("whisper_modell", "base"),
            opt.get("sprache"),
            # Abbruch-Callback für laufende Transkription
            abbruch_callback=lambda: abbruch_angefordert(jid)
        )
        abbruch_check(jid, "nach Transkription")
        fortschritt(jid, 70, "transkription")

        # ── Schritt 4: Kapitel ────────────────────────────
        abbruch_check(jid, "vor Kapitel-Erkennung")
        kap = kapitel_erkennen(segs, text) if opt.get("kapitel_erkennen", True) else []

        # ── Schritt 5: Zusammenfassung ────────────────────
        zf = ""
        if opt.get("zusammenfassung_erstellen", True):
            abbruch_check(jid, "vor Zusammenfassung")
            job_status_aktualisieren(ses, jid, "zusammenfassung", 80.0)
            fortschritt(jid, 80, "zusammenfassung")
            zf = zusammenfassung_erstellen(
                text,
                opt.get("zusammenfassung_stil", "stichpunkte"),
                info.get("title", "")
            )

        # ── Schritt 6: Podcast ────────────────────────────
        abbruch_check(jid, "vor Podcast-Export")
        pod = None
        if opt.get("podcast_erstellen"):
            pod = podcast_exportieren(audio, segs, kap, info, jid)

        # ── Speichern ─────────────────────────────────────
        video_daten_speichern(ses, jid, info, text, zf, kap, audio, pod)
        job_status_aktualisieren(ses, jid, "abgeschlossen", 100.0)
        fortschritt(jid, 100, "abgeschlossen")
        log.info(f"✅ Job {jid} abgeschlossen")

    except JobAbgebrochen as e:
        log.info(f"🛑 Job {jid} abgebrochen: {e}")
        job_status_aktualisieren(ses, jid, "abgebrochen", 0, "Vom Nutzer abgebrochen")
        fortschritt(jid, 0, "abgebrochen")
        abbruch_aufraeumen(jid)

    except Exception as e:
        log.error(f"❌ Fehler {jid}: {e}", exc_info=True)
        job_status_aktualisieren(ses, jid, "fehler", 0, str(e))
        fortschritt(jid, 0, "fehler")

    finally:
        ses.close()


def main():
    log.info("Worker gestartet – warte auf Jobs...")
    while True:
        gef = False
        for sq in SCHLANGEN:
            raw = r.lpop(sq)
            if raw:
                try:
                    d = json.loads(raw)
                    jid = d["job_id"]
                    # Sofort prüfen ob Job bereits abgebrochen wurde
                    if abbruch_angefordert(jid):
                        log.info(f"Job {jid} übersprungen – bereits abgebrochen")
                        abbruch_aufraeumen(jid)
                    else:
                        verarbeiten(jid, d.get("optionen", {}))
                except Exception as e:
                    log.error(f"Parse-Fehler: {e}")
                gef = True
                break
        if not gef:
            time.sleep(2)


if __name__ == "__main__":
    main()