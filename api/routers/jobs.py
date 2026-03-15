from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from database import get_db
from models import Job, Video, JobStatus
from schemas import JobErstellen, JobAntwort, VideoAntwort
from queue_manager import (
    job_einreihen, warteschlangen_laenge, fortschritt_abrufen,
    fortschritt_setzen, abbruch_signalisieren, aus_warteschlange_entfernen,
)
from uuid import UUID
from typing import List
import asyncio

router = APIRouter()

ABBRECHBAR = {"warteschlange","herunterladen","verarbeitung","transkription","zusammenfassung"}
LOESCHBAR  = {"abgeschlossen","fehler","abgebrochen"}


@router.post("/", response_model=JobAntwort)
async def job_erstellen(nutzlast: JobErstellen, db: AsyncSession = Depends(get_db)):
    job = Job(
        url=nutzlast.url,
        status="warteschlange",
        prioritaet=nutzlast.prioritaet,
        optionen={
            "url":                       nutzlast.url,
            "whisper_modell":            nutzlast.whisper_modell,
            "sprache":                   nutzlast.sprache,
            "zusammenfassung_erstellen": nutzlast.zusammenfassung_erstellen,
            "kapitel_erkennen":          nutzlast.kapitel_erkennen,
            "podcast_erstellen":         nutzlast.podcast_erstellen,
            "zusammenfassung_stil":      nutzlast.zusammenfassung_stil,
        }
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    job_einreihen(str(job.id), job.optionen, nutzlast.prioritaet)
    return job


@router.get("/", response_model=List[JobAntwort])
async def jobs_auflisten(
    limit: int = 50, versatz: int = 0,
    db: AsyncSession = Depends(get_db)
):
    ergebnis = await db.execute(
        select(Job).order_by(desc(Job.erstellt_am)).limit(limit).offset(versatz)
    )
    return ergebnis.scalars().all()


@router.get("/warteschlange/statistik")
async def warteschlange_statistik():
    return warteschlangen_laenge()


@router.delete("/batch/abgebrochen")
async def abgebrochene_loeschen(db: AsyncSession = Depends(get_db)):
    ergebnis = await db.execute(text("""
        DELETE FROM jobs
        WHERE status IN ('abgebrochen','fehler')
        RETURNING id
    """))
    geloescht = ergebnis.rowcount
    await db.commit()
    return {"geloescht": geloescht}


@router.get("/{job_id}", response_model=JobAntwort)
async def job_abrufen(job_id: UUID, db: AsyncSession = Depends(get_db)):
    ergebnis = await db.execute(select(Job).where(Job.id == job_id))
    job = ergebnis.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job nicht gefunden")
    return job


@router.get("/{job_id}/fortschritt")
async def fortschritt_abfragen(job_id: UUID):
    return fortschritt_abrufen(str(job_id))


@router.get("/{job_id}/video", response_model=VideoAntwort)
async def video_abrufen(job_id: UUID, db: AsyncSession = Depends(get_db)):
    ergebnis = await db.execute(select(Video).where(Video.job_id == job_id))
    video = ergebnis.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video nicht gefunden")
    return video


@router.post("/{job_id}/abbrechen")
async def job_abbrechen(job_id: UUID, db: AsyncSession = Depends(get_db)):
    ergebnis = await db.execute(select(Job).where(Job.id == job_id))
    job = ergebnis.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job nicht gefunden")

    job_id_str = str(job_id)
    aus_warteschlange_entfernen(job_id_str)
    abbruch_signalisieren(job_id_str)
    fortschritt_setzen(job_id_str, 0, "abgebrochen")

    await db.delete(job)
    await db.commit()
    return {"erfolg": True, "job_id": job_id_str}


@router.delete("/{job_id}")
async def job_loeschen(job_id: UUID, db: AsyncSession = Depends(get_db)):
    ergebnis = await db.execute(select(Job).where(Job.id == job_id))
    job = ergebnis.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job nicht gefunden")
    await db.delete(job)
    await db.commit()
    return {"geloescht": str(job_id)}


@router.websocket("/ws/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            daten = fortschritt_abrufen(job_id)
            await websocket.send_json(daten)
            if daten["status"] in ("abgeschlossen","fehler","abgebrochen"):
                break
            await asyncio.sleep(0.8)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws")
async def alle_jobs_websocket(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        while True:
            ergebnis = await db.execute(
                select(Job).order_by(desc(Job.erstellt_am)).limit(50)
            )
            jobs_liste = ergebnis.scalars().all()
            daten = [{
                "id":            str(j.id),
                "url":           j.url,
                "status":        j.status,
                "fortschritt":   j.fortschritt or 0,
                "erstellt_am":   j.erstellt_am.isoformat(),
                "fehlermeldung": j.fehlermeldung,
            } for j in jobs_liste]
            await websocket.send_json(daten)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass