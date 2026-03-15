#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Database Worker
Datenbankoperationen für den Worker
"""

import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("db_worker")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yt_user:sicheres_passwort@postgres:5432/yt_ai_suite")

try:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
    log.info("Datenbankverbindung erfolgreich hergestellt")
except Exception as e:
    log.error(f"Fehler beim Verbindungsaufbau zur Datenbank: {e}")
    engine = None

def get_db_connection():
    if not engine:
        raise Exception("Keine Datenbankverbindung verfügbar")
    return engine.connect()

def job_abgeschlossen(job_id: str, video_data: Dict[str, Any]):
    """
    Markiert einen Job als abgeschlossen und speichert die Video-Daten
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Prüfen ob Video bereits existiert
        existing = conn.execute(
            text("SELECT id FROM videos WHERE youtube_id = :youtube_id"),
            {"youtube_id": video_data.get('youtube_id')}
        ).fetchone()
        
        if existing:
            # Video existiert bereits - nur Job aktualisieren
            log.info(f"Video {video_data.get('youtube_id')} existiert bereits, überspringe INSERT")
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
            conn.execute(
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
                    )
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
        log.info(f"Job {job_id} erfolgreich als abgeschlossen gespeichert")
        
    except Exception as e:
        log.error(f"Fehler in job_abgeschlossen für {job_id}: {e}")
        if conn:
            conn.rollback()
        # Bei Duplikat-Fehler nicht weiterwerfen - Job ist trotzdem fertig
        if "duplicate key" in str(e):
            log.info(f"Video existiert bereits - Job {job_id} wird trotzdem als fertig betrachtet")
            # Job manuell als abgeschlossen markieren
            try:
                conn2 = get_db_connection()
                conn2.execute(
                    text("UPDATE jobs SET status = 'abgeschlossen', beendet_am = NOW() WHERE id = :job_id"),
                    {"job_id": job_id}
                )
                conn2.commit()
                conn2.close()
            except:
                pass
        else:
            raise
    finally:
        if conn:
            conn.close()

def job_fehler(job_id: str, fehlermeldung: str):
    """Markiert einen Job als fehlgeschlagen"""
    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            text("""
                UPDATE jobs 
                SET status = 'fehler', 
                    fehlermeldung = :fehlermeldung,
                    beendet_am = NOW()
                WHERE id = :job_id
            """),
            {"job_id": job_id, "fehlermeldung": fehlermeldung[:500]}
        )
        conn.commit()
        log.error(f"Job {job_id} als fehlerhaft markiert: {fehlermeldung}")
    except Exception as e:
        log.error(f"Fehler in job_fehler für {job_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def job_status_update(job_id: str, status: str):
    """Aktualisiert den Status eines Jobs"""
    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            text("UPDATE jobs SET status = :status WHERE id = :job_id"),
            {"job_id": job_id, "status": status}
        )
        conn.commit()
        log.debug(f"Job {job_id} Status aktualisiert: {status}")
    except Exception as e:
        log.error(f"Fehler in job_status_update für {job_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def job_fortschritt_update(job_id: str, fortschritt: float, status: str = None):
    """Aktualisiert den Fortschritt eines Jobs"""
    conn = None
    try:
        conn = get_db_connection()
        if status:
            conn.execute(
                text("UPDATE jobs SET fortschritt = :fortschritt, status = :status WHERE id = :job_id"),
                {"job_id": job_id, "fortschritt": fortschritt, "status": status}
            )
        else:
            conn.execute(
                text("UPDATE jobs SET fortschritt = :fortschritt WHERE id = :job_id"),
                {"job_id": job_id, "fortschritt": fortschritt}
            )
        conn.commit()
        log.debug(f"Job {job_id} Fortschritt: {fortschritt}%")
    except Exception as e:
        log.error(f"Fehler in job_fortschritt_update für {job_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def job_abbrechen_pruefen(job_id: str) -> bool:
    """Prüft ob ein Job abgebrochen werden soll"""
    conn = None
    try:
        conn = get_db_connection()
        result = conn.execute(
            text("SELECT status FROM jobs WHERE id = :job_id"),
            {"job_id": job_id}
        ).fetchone()
        return bool(result and result[0] == 'abgebrochen')
    except Exception as e:
        log.error(f"Fehler in job_abbrechen_pruefen für {job_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def queue_statistik() -> Dict[str, int]:
    """Gibt Queue-Statistiken zurück"""
    conn = None
    try:
        conn = get_db_connection()
        wartend = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = 'warteschlange'")
        ).scalar() or 0
        aktiv = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status IN ('herunterladen', 'verarbeitung', 'transkription', 'zusammenfassung')")
        ).scalar() or 0
        fehler = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = 'fehler'")
        ).scalar() or 0
        heute_abgeschlossen = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = 'abgeschlossen' AND DATE(beendet_am) = CURRENT_DATE")
        ).scalar() or 0
        return {
            "wartend": wartend,
            "aktiv": aktiv,
            "fehler": fehler,
            "heute_abgeschlossen": heute_abgeschlossen,
            "gesamt": wartend + aktiv + fehler
        }
    except Exception as e:
        log.error(f"Fehler in queue_statistik: {e}")
        return {"wartend": 0, "aktiv": 0, "fehler": 0, "heute_abgeschlossen": 0, "gesamt": 0}
    finally:
        if conn:
            conn.close()