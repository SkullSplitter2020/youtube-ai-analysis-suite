from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from database import get_db
from models import Video
from schemas import SucheAnfrage, SucheErgebnis
from typing import List

router = APIRouter()


@router.post("/", response_model=List[SucheErgebnis])
async def suchen(anfrage: SucheAnfrage, db: AsyncSession = Depends(get_db)):
    muster = f"%{anfrage.suchwort}%"
    ergebnis = await db.execute(
        select(Video).where(or_(
            Video.transkript.ilike(muster), Video.titel.ilike(muster),
            Video.beschreibung.ilike(muster), Video.zusammenfassung.ilike(muster),
        )).limit(anfrage.limit).offset(anfrage.versatz))
    videos = ergebnis.scalars().all()
    treffer = []
    for v in videos:
        gefunden_in, ausschnitt = "titel", v.titel or ""
        s = anfrage.suchwort.lower()
        if v.transkript and s in v.transkript.lower():
            gefunden_in = "transkript"
            idx = v.transkript.lower().find(s)
            ausschnitt = v.transkript[max(0, idx-80):idx+120]
        elif v.zusammenfassung and s in (v.zusammenfassung or "").lower():
            gefunden_in, ausschnitt = "zusammenfassung", v.zusammenfassung[:200]
        treffer.append(SucheErgebnis(video_id=v.id, job_id=v.job_id, titel=v.titel,
                                     kanal=v.kanal, gefunden_in=gefunden_in, ausschnitt=ausschnitt))
    return treffer
