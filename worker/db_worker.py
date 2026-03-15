from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid, json, os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yt_user:yt_geheim@postgres:5432/yt_ai_suite")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def db_session_erstellen():
    return SessionLocal()


def job_status_aktualisieren(session, job_id, status, fortschritt, fehler=None):
    jetzt = datetime.utcnow()
    if status in ("abgeschlossen", "fehler"):
        session.execute(text(
            "UPDATE jobs SET status=:s, fortschritt=:p, beendet_am=:f, fehlermeldung=:e WHERE id=:id"),
            {"s": status, "p": fortschritt, "f": jetzt, "e": fehler, "id": job_id})
    elif status == "herunterladen":
        session.execute(text(
            "UPDATE jobs SET status=:s, fortschritt=:p, gestartet_am=:st WHERE id=:id"),
            {"s": status, "p": fortschritt, "st": jetzt, "id": job_id})
    else:
        session.execute(text(
            "UPDATE jobs SET status=:s, fortschritt=:p WHERE id=:id"),
            {"s": status, "p": fortschritt, "id": job_id})
    session.commit()


def video_daten_speichern(session, job_id, info, transkript, zusammenfassung, kapitel, audio, podcast):
    vid = str(uuid.uuid4())
    session.execute(text(
        "INSERT INTO videos (id, job_id, youtube_id, titel, beschreibung, kanal, dauer,"
        " hochladedatum, thumbnail_url, transkript, zusammenfassung,"
        " kapitel, audio_pfad, podcast_pfad, erstellt_am)"
        " VALUES (:id,:jid,:yid,:t,:b,:k,:d,:hd,:th,:tr,:zf,:kp::jsonb,:ap,:pp,:now)"
        " ON CONFLICT (youtube_id) DO UPDATE SET"
        " transkript=EXCLUDED.transkript, zusammenfassung=EXCLUDED.zusammenfassung,"
        " kapitel=EXCLUDED.kapitel, audio_pfad=EXCLUDED.audio_pfad"
    ), {"id":vid,"jid":job_id,"yid":info.get("id",""),
        "t":info.get("title",""),"b":(info.get("description","") or "")[:4000],
        "k":info.get("uploader",""),"d":info.get("duration",0),
        "hd":info.get("upload_date",""),"th":info.get("thumbnail",""),
        "tr":transkript,"zf":zusammenfassung,"kp":json.dumps(kapitel),
        "ap":audio,"pp":podcast,"now":datetime.utcnow()})
    session.commit()
