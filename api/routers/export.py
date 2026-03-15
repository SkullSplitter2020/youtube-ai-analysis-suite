from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Video
from uuid import UUID
import os

router = APIRouter()


@router.get("/{job_id}/txt", response_class=PlainTextResponse)
async def als_txt(job_id: UUID, db: AsyncSession = Depends(get_db)):
    v = await _video(job_id, db)
    inhalt = f"Titel: {v.titel}\nKanal: {v.kanal}\n\n=== TRANSKRIPT ===\n\n{v.transkript or 'N/A'}"
    if v.zusammenfassung:
        inhalt += f"\n\n=== ZUSAMMENFASSUNG ===\n\n{v.zusammenfassung}"
    return inhalt


@router.get("/{job_id}/markdown", response_class=PlainTextResponse)
async def als_md(job_id: UUID, db: AsyncSession = Depends(get_db)):
    v = await _video(job_id, db)
    z = [f"# {v.titel}", f"**Kanal:** {v.kanal}", ""]
    if v.zusammenfassung:
        z += ["## Zusammenfassung", v.zusammenfassung, ""]
    if v.kapitel:
        z += ["## Kapitel"]
        for k in v.kapitel:
            z.append(f"- `{k.get('zeitstempel','')}` {k.get('titel','')}")
        z.append("")
    if v.transkript:
        z += ["## Transkript", v.transkript]
    return "\n".join(z)


@router.get("/{job_id}/json")
async def als_json(job_id: UUID, db: AsyncSession = Depends(get_db)):
    v = await _video(job_id, db)
    return {"titel": v.titel, "kanal": v.kanal, "dauer": v.dauer,
            "transkript": v.transkript, "zusammenfassung": v.zusammenfassung, "kapitel": v.kapitel}


@router.get("/{job_id}/podcast")
async def podcast(job_id: UUID, db: AsyncSession = Depends(get_db)):
    v = await _video(job_id, db)
    if not v.podcast_pfad or not os.path.exists(v.podcast_pfad):
        raise HTTPException(404, "Podcast nicht erstellt")
    return FileResponse(v.podcast_pfad, media_type="audio/mpeg",
                        filename=f"{v.youtube_id}_podcast.mp3")


async def _video(job_id, db):
    e = await db.execute(select(Video).where(Video.job_id == job_id))
    v = e.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Video nicht gefunden")
    return v
