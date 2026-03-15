#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Database Worker
Optimierte Version mit sicherem Löschen und UPSERT
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("db_worker")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://yt_user:sicheres_passwort@postgres:5432/yt_ai_suite"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)


# --------------------------------------------------
# Datenbank Helper
# --------------------------------------------------

def get_db_connection():
    return engine.connect()


def execute(query, params=None):
    with engine.begin() as conn:
        return conn.execute(text(query), params or {})


# --------------------------------------------------
# Job komplett löschen
# --------------------------------------------------

def job_komplett_loeschen(job_id: str):

    conn = None

    try:

        conn = get_db_connection()

        video = conn.execute(
            text("SELECT audio_pfad, podcast_pfad FROM videos WHERE job_id=:job_id"),
            {"job_id": job_id}
        ).fetchone()

        conn.execute(
            text("DELETE FROM jobs WHERE id=:job_id"),
            {"job_id": job_id}
        )

        conn.commit()

        # Dateien löschen
        paths = []

        if video:
            if video[0]:
                paths.append(Path(video[0]))

            if video[1]:
                paths.append(Path(video[1]))

        paths.extend([
            Path(f"/app/data/transcripts/{job_id}.txt"),
            Path(f"/app/data/summaries/{job_id}.txt"),
            Path(f"/app/data/chapters/{job_id}.json"),
            Path(f"/app/data/podcasts/{job_id}.mp3")
        ])

        for p in paths:
            try:
                if p.exists():
                    p.unlink()
                    log.info(f"🗑️ Datei gelöscht: {p}")
            except Exception as e:
                log.warning(f"Datei konnte nicht gelöscht werden: {p} ({e})")

        job_dir = Path(f"/app/data/audio/{job_id}")

        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            log.info(f"🗑️ Job Verzeichnis gelöscht: {job_dir}")

        log.info(f"✅ Job {job_id} komplett gelöscht")

        return True

    except Exception as e:

        log.error(f"Fehler beim Löschen von Job {job_id}: {e}")

        if conn:
            conn.rollback()

        return False

    finally:

        if conn:
            conn.close()


# --------------------------------------------------
# Batch löschen
# --------------------------------------------------

def batch_loesche_fehlerhafte():

    conn = None

    try:

        conn = get_db_connection()

        jobs = conn.execute(
            text("SELECT id FROM jobs WHERE status IN ('fehler','abgebrochen')")
        ).fetchall()

        job_ids = [str(j[0]) for j in jobs]

        if not job_ids:
            log.info("Keine fehlerhaften Jobs gefunden")
            return 0

        log.info(f"Lösche {len(job_ids)} Jobs...")

        gelöscht = 0

        for job_id in job_ids:

            if job_komplett_loeschen(job_id):
                gelöscht += 1

        log.info(f"✅ {gelöscht} Jobs gelöscht")

        return gelöscht

    except Exception as e:

        log.error(f"Batch Löschen Fehler: {e}")
        return 0

    finally:

        if conn:
            conn.close()


# --------------------------------------------------
# Job abgeschlossen
# --------------------------------------------------

def job_abgeschlossen(job_id: str, video_data: Dict[str, Any]):
    """
    Markiert einen Job als abgeschlossen und speichert die Video-Daten
    VERBESSERTE VERSION mit besserer Fehlerbehandlung
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Prüfen ob Video bereits existiert
        youtube_id = video_data.get('youtube_id')
        existing = None
        if youtube_id:
            existing = conn.execute(
                text("SELECT id FROM videos WHERE youtube_id = :youtube_id"),
                {"youtube_id": youtube_id}
            ).fetchone()
        
        if existing:
            # Video existiert bereits - nur Job aktualisieren
            log.info(f"Video {youtube_id} existiert bereits, überspringe INSERT")
            conn.execute(
                text("""
                    UPDATE jobs 
                    SET status = 'abgeschlossen', 
                        fortschritt = 100.0,
                        beendet_am = NOW()
                    WHERE id = :job_id
                """),
                {"job_id": job_id}
            )
        else:
            # Neues Video einfügen
            log.info(f"Speichere neues Video für Job {job_id}")
            result = conn.execute(
                text("""
                    INSERT INTO videos (
                        id, job_id, youtube_id, titel, beschreibung, 
                        kanal, dauer, hochladedatum, thumbnail_url,
                        transkript, zusammenfassung, kapitel, 
                        audio_pfad, podcast_pfad, erstellt_am
                    ) VALUES (
                        gen_random_uuid(), :job_id, :youtube_id, :titel, :beschreibung,
                        :kanal, :dauer, :hochladedatum, :thumbnail_url,
                        :transkript, :zusammenfassung, :kapitel,
                        :audio_pfad, :podcast_pfad, NOW()
                    ) RETURNING id
                """),
                {
                    "job_id": job_id,
                    "youtube_id": video_data.get('youtube_id'),
                    "titel": video_data.get('titel', 'Unbekannter Titel'),
                    "beschreibung": video_data.get('beschreibung', ''),
                    "kanal": video_data.get('kanal', ''),
                    "dauer": video_data.get('dauer', 0),
                    "hochladedatum": video_data.get('hochladedatum', ''),
                    "thumbnail_url": video_data.get('thumbnail_url', ''),
                    "transkript": video_data.get('transkript', ''),
                    "zusammenfassung": video_data.get('zusammenfassung', ''),
                    "kapitel": video_data.get('kapitel', '[]'),
                    "audio_pfad": video_data.get('audio_pfad', ''),
                    "podcast_pfad": video_data.get('podcast_pfad', '')
                }
            )
            video_id = result.fetchone()[0]
            log.info(f"Video {video_id} für Job {job_id} gespeichert")
            
            # Job-Status aktualisieren
            conn.execute(
                text("""
                    UPDATE jobs 
                    SET status = 'abgeschlossen', 
                        fortschritt = 100.0,
                        beendet_am = NOW()
                    WHERE id = :job_id
                """),
                {"job_id": job_id}
            )
        
        conn.commit()
        log.info(f"✅ Job {job_id} erfolgreich als abgeschlossen gespeichert")
        return True
        
    except Exception as e:
        log.error(f"❌ Fehler in job_abgeschlossen für {job_id}: {e}")
        if conn:
            conn.rollback()
        # Bei Duplikat-Fehler nicht weiterwerfen - Job ist trotzdem fertig
        if "duplicate key" in str(e):
            log.info(f"Video existiert bereits - Job {job_id} wird trotzdem als fertig betrachtet")
            try:
                conn2 = get_db_connection()
                conn2.execute(
                    text("UPDATE jobs SET status = 'abgeschlossen', beendet_am = NOW() WHERE id = :job_id"),
                    {"job_id": job_id}
                )
                conn2.commit()
                conn2.close()
                return True
            except:
                pass
        return False
    finally:
        if conn:
            conn.close()


# --------------------------------------------------
# Fehler
# --------------------------------------------------

def job_fehler(job_id: str, msg: str):

    execute(
        """
        UPDATE jobs
        SET status='fehler',
            fehlermeldung=:msg,
            beendet_am=NOW()
        WHERE id=:id
        """,
        {
            "id": job_id,
            "msg": msg[:500]
        }
    )


# --------------------------------------------------
# Status Update
# --------------------------------------------------

def job_status_update(job_id: str, status: str):

    execute(
        "UPDATE jobs SET status=:status WHERE id=:id",
        {
            "id": job_id,
            "status": status
        }
    )


# --------------------------------------------------
# Fortschritt
# --------------------------------------------------

def job_fortschritt_update(job_id: str, fortschritt: float, status: str = None):

    if status:

        execute(
            """
            UPDATE jobs
            SET fortschritt=:fortschritt,
                status=:status
            WHERE id=:id
            """,
            {
                "id": job_id,
                "fortschritt": fortschritt,
                "status": status
            }
        )

    else:

        execute(
            """
            UPDATE jobs
            SET fortschritt=:fortschritt
            WHERE id=:id
            """,
            {
                "id": job_id,
                "fortschritt": fortschritt
            }
        )