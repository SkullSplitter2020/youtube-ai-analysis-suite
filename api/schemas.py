from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# String statt Enum – direkt die DB-Werte nutzen
class JobErstellen(BaseModel):
    url: str
    whisper_modell: str = "base"
    sprache: Optional[str] = None
    zusammenfassung_erstellen: bool = True
    kapitel_erkennen: bool = True
    podcast_erstellen: bool = False
    zusammenfassung_stil: str = "stichpunkte"
    prioritaet: int = 0


class JobAntwort(BaseModel):
    id: UUID
    url: str
    status: str          # ← String statt Enum
    fortschritt: float
    fehlermeldung: Optional[str]
    erstellt_am: datetime
    gestartet_am: Optional[datetime]
    beendet_am: Optional[datetime]

    class Config:
        from_attributes = True


class VideoAntwort(BaseModel):
    id: UUID
    job_id: UUID
    youtube_id: str
    titel: str
    kanal: str
    dauer: int
    hochladedatum: str
    thumbnail_url: Optional[str]
    transkript: Optional[str]
    zusammenfassung: Optional[str]
    kapitel: Optional[List[Dict[str, Any]]]
    audio_pfad: Optional[str]
    podcast_pfad: Optional[str]

    class Config:
        from_attributes = True


class SucheAnfrage(BaseModel):
    suchwort: str
    limit: int = 20
    versatz: int = 0


class SucheErgebnis(BaseModel):
    video_id: UUID
    job_id: UUID
    titel: str
    kanal: str
    gefunden_in: str
    ausschnitt: str