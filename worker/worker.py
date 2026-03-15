#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Worker (Optimierte Version)
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

log = logging.getLogger("worker")

# DB
from db_worker import (
    job_abgeschlossen,
    job_fehler,
    job_status_update,
    job_fortschritt_update,
)

# Redis
import redis.asyncio as redis

# Pipeline
from pipeline.downloader import YouTubeDownloader
from pipeline.audio_processor import AudioProcessor
from pipeline.transcriber import WhisperTranscriber
from pipeline.chapter_detector import ChapterDetector
from pipeline.summarizer import OllamaSummarizer
from pipeline.podcast_exporter import PodcastExporter


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODELL", "llama3.2:1b")

WHISPER_MODEL = os.getenv("WHISPER_MODELL", "tiny")
WHISPER_DEVICE = os.getenv("WHISPER_GERAET", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_BERECHNUNG", "int8")

AUDIO_PATH = "/app/data/audio"
TRANSCRIPTS_PATH = "/app/data/transcripts"
SUMMARIES_PATH = "/app/data/summaries"
CHAPTERS_PATH = "/app/data/chapters"
PODCASTS_PATH = "/app/data/podcasts"

for path in [AUDIO_PATH, TRANSCRIPTS_PATH, SUMMARIES_PATH, CHAPTERS_PATH, PODCASTS_PATH]:
    os.makedirs(path, exist_ok=True)


class YouTubeWorker:

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.running = True
        self.current_job = None
        self.jobs_processed = 0
        self.start_time = datetime.now()

        self.redis = None

        self.downloader = YouTubeDownloader()
        self.audio_processor = AudioProcessor()

        self.transcriber = WhisperTranscriber(
            model_size=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        )

        self.chapter_detector = ChapterDetector()

        self.summarizer = OllamaSummarizer(
            OLLAMA_URL,
            OLLAMA_MODEL,
            timeout=120
        )

        self.podcast_exporter = PodcastExporter()

        log.info(f"Worker gestartet: {worker_id}")


    async def connect_redis(self):
        self.redis = await redis.from_url(
            REDIS_URL,
            decode_responses=True
        )


    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        try:
            for queue in ["yt_jobs_prioritaet", "yt_jobs_normal"]:
                job_data = await self.redis.lpop(queue)

                if job_data:
                    job = json.loads(job_data)

                    job_id = job.get("id") or job.get("job_id")

                    if not job_id:
                        continue

                    job["id"] = job_id

                    await self.redis.setex(
                        f"job:{job_id}:processing",
                        300,
                        self.worker_id
                    )

                    log.info(f"Job übernommen: {job_id}")
                    return job

            return None

        except Exception as e:
            log.error(f"Queue Fehler: {e}")
            return None


    async def update_progress(self, job_id: str, progress: float, status: str):

        try:
            job_fortschritt_update(job_id, progress, status)

            await self.redis.setex(
                f"fortschritt:{job_id}",
                3600,
                json.dumps({
                    "fortschritt": progress,
                    "status": status
                })
            )

        except Exception as e:
            log.error(f"Progress Fehler: {e}")


    async def check_abort(self, job_id: str) -> bool:

        try:
            return bool(await self.redis.exists(f"abbruch:{job_id}"))
        except:
            return False


    async def process_job(self, job: Dict[str, Any]):

        job_id = job["id"]
        url = job.get("url") or job.get("optionen", {}).get("url", "")
        options = job.get("optionen", {})

        log.info(f"Starte Job {job_id}")

        try:

            await self.update_progress(job_id, 5, "herunterladen")

            video_info = await self.downloader.download_video(
                url,
                job_id,
                AUDIO_PATH
            )

            if await self.check_abort(job_id):
                return


            audio_file = video_info.get("audio_pfad")

            if audio_file:

                await self.update_progress(job_id, 20, "verarbeitung")

                audio_file = await self.audio_processor.process(
                    audio_file,
                    job_id
                )


            transcript = ""

            if audio_file:

                await self.update_progress(job_id, 35, "transkription")

                async def progress_callback(p):

                    if p is None:
                        return

                    await self.update_progress(
                        job_id,
                        35 + (p * 35),
                        "transkription"
                    )


                transcript = await self.transcriber.transcribe(
                    audio_file,
                    job_id,
                    progress_callback
                )


            chapters = []

            if transcript:

                await self.update_progress(job_id, 72, "verarbeitung")

                chapters = await self.chapter_detector.detect(
                    transcript,
                    audio_file
                )


            summary = ""

            if options.get("zusammenfassung_erstellen", True):

                await self.update_progress(job_id, 80, "zusammenfassung")

                try:

                    summary = await self.summarizer.summarize(
                        transcript,
                        options.get("zusammenfassung_stil", "stichpunkte"),
                        job_id
                    )

                except Exception as e:

                    log.error(f"Zusammenfassung fehlgeschlagen: {e}")

                    summary = ""

            video_data = {

                "job_id": job_id,

                **video_info,

                "transkript": transcript,
                "zusammenfassung": summary,
                "kapitel": json.dumps(chapters),

                "audio_pfad": audio_file,
                "podcast_pfad": None
            
}
            job_abgeschlossen(job_id, video_data)

            self.jobs_processed += 1

            log.info(f"Job fertig: {job_id}")

        except Exception as e:

            log.error(f"Job Fehler {job_id}: {e}")

            job_fehler(job_id, str(e)[:200])


    async def run_forever(self):

        await self.connect_redis()

        log.info("Worker läuft")

        while self.running:

            try:

                job = await self.get_next_job()

                if job:

                    self.current_job = job["id"]

                    await self.process_job(job)

                    self.current_job = None

                else:
                    await asyncio.sleep(5)

            except Exception as e:

                log.error(f"Loop Fehler: {e}")

                await asyncio.sleep(5)


    async def shutdown(self):

        log.info("Worker Shutdown")

        self.running = False

        if self.current_job:
            job_status_update(self.current_job, "abgebrochen")

        if self.redis:
            await self.redis.close()


async def main():

    worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")

    worker = YouTubeWorker(worker_id)

    try:

        await worker.run_forever()

    except KeyboardInterrupt:

        await worker.shutdown()

    except Exception as e:

        log.error(f"Kritischer Fehler:\n{traceback.format_exc()}")

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())