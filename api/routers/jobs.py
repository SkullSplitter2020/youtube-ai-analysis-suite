from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from database import get_db
from models import Job, Video
from schemas import JobErstellen, JobAntwort, VideoAntwort
from queue_manager import (
    job_einreihen, warteschlangen_laenge, fortschritt_abrufen,
    fortschritt_setzen, abbruch_signalisieren, aus_warteschlange_entfernen
)

from uuid import UUID
from typing import List
import asyncio
import logging
from pathlib import Path
import shutil


router = APIRouter()
log = logging.getLogger("api_jobs")


# --------------------------------------------------
# Dateien löschen
# --------------------------------------------------

async def delete_job_files(job_id: str):

    paths = [
        Path(f"/app/data/audio/{job_id}"),
        Path(f"/app/data/transcripts/{job_id}.txt"),
        Path(f"/app/data/summaries/{job_id}.txt"),
        Path(f"/app/data/chapters/{job_id}.json"),
        Path(f"/app/data/podcasts/{job_id}.mp3")
    ]

    deleted = []

    for path in paths:
        try:

            if path.exists():

                if path.is_dir():
                    shutil.rmtree(path)

                else:
                    path.unlink()

                deleted.append(str(path))

        except Exception as e:

            log.warning(f"Datei konnte nicht gelöscht werden {path}: {e}")

    if deleted:
        log.info(f"Dateien gelöscht für Job {job_id}: {deleted}")

    return deleted


# --------------------------------------------------
# Job erstellen
# --------------------------------------------------

@router.post("/", response_model=JobAntwort)
async def job_erstellen(nutzlast: JobErstellen, db: AsyncSession = Depends(get_db)):

    job = Job(
        url=nutzlast.url,
        status="warteschlange",
        prioritaet=nutzlast.prioritaet,
        optionen={
            "url": nutzlast.url,
            "whisper_modell": nutzlast.whisper_modell,
            "sprache": nutzlast.sprache,
            "zusammenfassung_erstellen": nutzlast.zusammenfassung_erstellen,
            "kapitel_erkennen": nutzlast.kapitel_erkennen,
            "podcast_erstellen": nutzlast.podcast_erstellen,
            "zusammenfassung_stil": nutzlast.zusammenfassung_stil,
        }
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_einreihen(str(job.id), job.optionen, nutzlast.prioritaet)

    return job


# --------------------------------------------------
# Jobs Liste
# --------------------------------------------------

@router.get("/", response_model=List[JobAntwort])
async def jobs_auflisten(
    limit: int = 50,
    versatz: int = 0,
    db: AsyncSession = Depends(get_db)
):

    ergebnis = await db.execute(
        select(Job)
        .order_by(desc(Job.erstellt_am))
        .limit(limit)
        .offset(versatz)
    )

    return ergebnis.scalars().all()


# --------------------------------------------------
# Warteschlange Statistik
# --------------------------------------------------

@router.get("/warteschlange/statistik")
async def warteschlange_statistik():
    return warteschlangen_laenge()


# --------------------------------------------------
# Job abrufen
# --------------------------------------------------

@router.get("/{job_id}", response_model=JobAntwort)
async def job_abrufen(job_id: UUID, db: AsyncSession = Depends(get_db)):

    ergebnis = await db.execute(select(Job).where(Job.id == job_id))
    job = ergebnis.scalar_one_or_none()

    if not job:
        raise HTTPException(404, "Job nicht gefunden")

    return job


# --------------------------------------------------
# Fortschritt
# --------------------------------------------------

@router.get("/{job_id}/fortschritt")
async def fortschritt_abfragen(job_id: UUID):

    return fortschritt_abrufen(str(job_id))


# --------------------------------------------------
# Video abrufen
# --------------------------------------------------

@router.get("/{job_id}/video", response_model=VideoAntwort)
async def video_abrufen(job_id: UUID, db: AsyncSession = Depends(get_db)):

    ergebnis = await db.execute(
        select(Video).where(Video.job_id == job_id)
    )

    video = ergebnis.scalar_one_or_none()

    if not video:
        raise HTTPException(404, "Video nicht gefunden")

    return video


# --------------------------------------------------
# Job abbrechen
# --------------------------------------------------

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

    await delete_job_files(job_id_str)

    await db.delete(job)
    await db.commit()

    return {"erfolg": True, "job_id": job_id_str}


# --------------------------------------------------
# Job löschen
# --------------------------------------------------

@router.delete("/{job_id}")
async def job_loeschen(job_id: UUID, db: AsyncSession = Depends(get_db)):

    ergebnis = await db.execute(select(Job).where(Job.id == job_id))
    job = ergebnis.scalar_one_or_none()

    if not job:
        raise HTTPException(404, "Job nicht gefunden")

    job_id_str = str(job_id)

    await delete_job_files(job_id_str)

    await db.delete(job)
    await db.commit()

    return {"geloescht": job_id_str}


# --------------------------------------------------
# Batch löschen
# --------------------------------------------------

@router.delete("/batch/abgebrochen")
async def batch_delete_failed(db: AsyncSession = Depends(get_db)):

    ergebnis = await db.execute(
        select(Job).where(Job.status.in_(["fehler", "abgebrochen"]))
    )

    jobs = ergebnis.scalars().all()

    deleted = []

    for job in jobs:

        job_id = str(job.id)

        await delete_job_files(job_id)

        await db.delete(job)

        deleted.append(job_id)

    await db.commit()

    return {
        "status": "ok",
        "gelöscht": len(deleted),
        "jobs": deleted
    }


# --------------------------------------------------
# WebSocket Job
# --------------------------------------------------

@router.websocket("/ws/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):

    await websocket.accept()

    try:

        while True:

            daten = fortschritt_abrufen(job_id)

            await websocket.send_json(daten)

            if daten["status"] in ("abgeschlossen", "fehler", "abgebrochen"):
                break

            await asyncio.sleep(0.8)

    except WebSocketDisconnect:
        pass


# --------------------------------------------------
# WebSocket alle Jobs
# --------------------------------------------------

@router.websocket("/ws")
async def alle_jobs_websocket(websocket: WebSocket, db: AsyncSession = Depends(get_db)):

    await websocket.accept()

    try:

        while True:

            ergebnis = await db.execute(
                select(Job)
                .order_by(desc(Job.erstellt_am))
                .limit(50)
            )

            jobs_liste = ergebnis.scalars().all()

            daten = [
                {
                    "id": str(j.id),
                    "url": j.url,
                    "status": j.status,
                    "fortschritt": j.fortschritt or 0,
                    "erstellt_am": j.erstellt_am.isoformat(),
                    "fehlermeldung": j.fehlermeldung,
                }
                for j in jobs_liste
            ]

            await websocket.send_json(daten)

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass