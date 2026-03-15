from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from datetime import datetime
import uuid
import enum


class JobStatus(str, enum.Enum):
    WARTESCHLANGE   = "warteschlange"
    HERUNTERLADEN   = "herunterladen"
    VERARBEITUNG    = "verarbeitung"
    TRANSKRIPTION   = "transkription"
    ZUSAMMENFASSUNG = "zusammenfassung"
    ABGESCHLOSSEN   = "abgeschlossen"
    FEHLER          = "fehler"
    ABGEBROCHEN     = "abgebrochen"


# Enum-Typ explizit mit Kleinbuchstaben definieren
jobstatus_typ = SAEnum(
    "warteschlange",
    "herunterladen",
    "verarbeitung",
    "transkription",
    "zusammenfassung",
    "abgeschlossen",
    "fehler",
    "abgebrochen",
    name="jobstatus"
)


class Job(Base):
    __tablename__ = "jobs"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url           = Column(String(2048), nullable=False)
    status        = Column(jobstatus_typ, default="warteschlange", index=True)
    prioritaet    = Column(Integer, default=0)
    optionen      = Column(JSON, default={})
    fehlermeldung = Column(Text, nullable=True)
    fortschritt   = Column(Float, default=0.0)
    erstellt_am   = Column(DateTime, default=datetime.utcnow)
    gestartet_am  = Column(DateTime, nullable=True)
    beendet_am    = Column(DateTime, nullable=True)


class Video(Base):
    __tablename__ = "videos"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id          = Column(UUID(as_uuid=True), nullable=False, index=True)
    youtube_id      = Column(String(20), unique=True, index=True)
    titel           = Column(String(512))
    beschreibung    = Column(Text, nullable=True)
    kanal           = Column(String(256))
    dauer           = Column(Integer)
    hochladedatum   = Column(String(20))
    thumbnail_url   = Column(String(2048), nullable=True)
    transkript      = Column(Text, nullable=True)
    zusammenfassung = Column(Text, nullable=True)
    kapitel         = Column(JSON, nullable=True)
    audio_pfad      = Column(String(512), nullable=True)
    podcast_pfad    = Column(String(512), nullable=True)
    erstellt_am     = Column(DateTime, default=datetime.utcnow)