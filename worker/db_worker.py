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
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# Umgebungsvariablen laden
load_dotenv()

# Logging Konfiguration
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("db_worker")

# Datenbankverbindung
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yt_user:pass@postgres:5432/yt_ai_suite")

# Engine erstellen (synchron für Worker)
try:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True  # Prüft Verbindung vor Verwendung
    )
    log.info("Datenbankverbindung erfolgreich hergestellt")
except Exception as e:
    log.error(f"Fehler beim Verbindungsaufbau zur Datenbank: {e}")
    engine = None

def get_db_connection():
    """Gibt eine Datenbankverbindung zurück"""
    if not engine:
        raise Exception("Keine Datenbankverbindung verfügbar")
    return engine.connect()

# ============================================================================
# JOB-Funktionen
# ============================================================================

def job_abgeschlossen(job_id: str, video_data: Dict[str, Any]):
    """
    Markiert einen Job als abgeschlossen und speichert die Video-Daten
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Video in Datenbank speichern
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
        raise
    finally:
        if conn:
            conn.close()

def job_fehler(job_id: str, fehlermeldung: str):
    """
    Markiert einen Job als fehlgeschlagen
    """
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
            {
                "job_id": job_id,
                "fehlermeldung": fehlermeldung[:500]  # Begrenzung
            }
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

def job_abbrechen(job_id: str):
    """
    Markiert einen Job als abgebrochen
    """
    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            text("""
                UPDATE jobs 
                SET status = 'abgebrochen',
                    beendet_am = NOW()
                WHERE id = :job_id
            """),
            {"job_id": job_id}
        )
        conn.commit()
        log.info(f"Job {job_id} wurde abgebrochen")
    except Exception as e:
        log.error(f"Fehler in job_abbrechen für {job_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def job_status_update(job_id: str, status: str):
    """
    Aktualisiert den Status eines Jobs
    """
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
    """
    Aktualisiert den Fortschritt eines Jobs
    """
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
    """
    Prüft ob ein Job abgebrochen werden soll
    """
    conn = None
    try:
        conn = get_db_connection()
        result = conn.execute(
            text("SELECT status FROM jobs WHERE id = :job_id"),
            {"job_id": job_id}
        ).fetchone()
        
        if result and result[0] == 'abgebrochen':
            log.info(f"Job {job_id} wurde abgebrochen")
            return True
        return False
    except Exception as e:
        log.error(f"Fehler in job_abbrechen_pruefen für {job_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def job_gestartet(job_id: str):
    """
    Markiert einen Job als gestartet
    """
    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            text("UPDATE jobs SET status = 'herunterladen', gestartet_am = NOW() WHERE id = :job_id"),
            {"job_id": job_id}
        )
        conn.commit()
        log.info(f"Job {job_id} gestartet")
    except Exception as e:
        log.error(f"Fehler in job_gestartet für {job_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# ============================================================================
# Video-Funktionen
# ============================================================================

def video_abrufen(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Ruft Video-Daten für einen Job ab
    """
    conn = None
    try:
        conn = get_db_connection()
        result = conn.execute(
            text("""
                SELECT * FROM videos 
                WHERE job_id = :job_id
            """),
            {"job_id": job_id}
        ).fetchone()
        
        if result:
            # Dict aus Row erstellen
            columns = result._fields
            return dict(zip(columns, result))
        return None
    except Exception as e:
        log.error(f"Fehler in video_abrufen für {job_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def video_suche(suchbegriff: str) -> list:
    """
    Volltextsuche in Videos
    """
    conn = None
    try:
        conn = get_db_connection()
        result = conn.execute(
            text("""
                SELECT v.*, j.url, j.erstellt_am as job_erstellt_am
                FROM videos v
                JOIN jobs j ON v.job_id = j.id
                WHERE 
                    v.titel ILIKE :suchbegriff OR
                    v.beschreibung ILIKE :suchbegriff OR
                    v.transkript ILIKE :suchbegriff OR
                    v.zusammenfassung ILIKE :suchbegriff OR
                    v.kanal ILIKE :suchbegriff
                ORDER BY v.erstellt_am DESC
                LIMIT 50
            """),
            {"suchbegriff": f"%{suchbegriff}%"}
        ).fetchall()
        
        videos = []
        for row in result:
            columns = row._fields
            videos.append(dict(zip(columns, row)))
        return videos
    except Exception as e:
        log.error(f"Fehler in video_suche: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ============================================================================
# Queue-Funktionen
# ============================================================================

def queue_statistik() -> Dict[str, int]:
    """
    Gibt Queue-Statistiken zurück
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Wartende Jobs in DB zählen
        wartend = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = 'warteschlange'")
        ).scalar()
        
        # Aktive Jobs
        aktiv = conn.execute(
            text("""
                SELECT COUNT(*) FROM jobs 
                WHERE status IN ('herunterladen', 'verarbeitung', 'transkription', 'zusammenfassung')
            """)
        ).scalar()
        
        # Fehlerhafte Jobs
        fehler = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = 'fehler'")
        ).scalar()
        
        # Abgeschlossene Jobs heute
        heute_abgeschlossen = conn.execute(
            text("""
                SELECT COUNT(*) FROM jobs 
                WHERE status = 'abgeschlossen' 
                AND DATE(beendet_am) = CURRENT_DATE
            """)
        ).scalar()
        
        return {
            "wartend": wartend or 0,
            "aktiv": aktiv or 0,
            "fehler": fehler or 0,
            "heute_abgeschlossen": heute_abgeschlossen or 0,
            "gesamt": (wartend or 0) + (aktiv or 0) + (fehler or 0)
        }
    except Exception as e:
        log.error(f"Fehler in queue_statistik: {e}")
        return {
            "wartend": 0,
            "aktiv": 0,
            "fehler": 0,
            "heute_abgeschlossen": 0,
            "gesamt": 0
        }
    finally:
        if conn:
            conn.close()

# ============================================================================
# Cleanup-Funktionen
# ============================================================================

def alte_jobs_aufraeumen(tage: int = 30):
    """
    Löscht alte abgeschlossene Jobs (optional)
    """
    conn = None
    try:
        conn = get_db_connection()
        
        # Alte Jobs finden
        result = conn.execute(
            text("""
                DELETE FROM jobs 
                WHERE status IN ('abgeschlossen', 'fehler', 'abgebrochen')
                AND beendet_am < NOW() - INTERVAL ':tage days'
                RETURNING id
            """),
            {"tage": tage}
        )
        
        gelöscht = result.rowcount
        conn.commit()
        
        if gelöscht > 0:
            log.info(f"{gelöscht} alte Jobs gelöscht (älter als {tage} Tage)")
        
        return gelöscht
    except Exception as e:
        log.error(f"Fehler in alte_jobs_aufraeumen: {e}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

# Initialisierung testen
if __name__ == "__main__":
    """Test der Datenbankverbindung"""
    try:
        conn = get_db_connection()
        result = conn.execute(text("SELECT 1")).scalar()
        print(f"✅ Datenbankverbindung OK: {result}")
        
        # Queue-Statistik testen
        stats = queue_statistik()
        print(f"📊 Queue-Statistik: {stats}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Fehler: {e}")