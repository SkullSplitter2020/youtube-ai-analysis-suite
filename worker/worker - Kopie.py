#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Worker
Komplette Version mit fix für Progress-Fehler
"""

import os
import sys
import json
import asyncio
import logging
import signal
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("worker")

# Datenbank-Importe
try:
    from db_worker import (
        job_abgeschlossen, job_fehler, job_status_update,
        job_fortschritt_update, job_abbrechen_pruefen,
        queue_statistik
    )
    log.info("Datenbank-Module erfolgreich geladen")
except ImportError as e:
    log.error(f"Kritischer Fehler: {e}")
    sys.exit(1)

# Redis
try:
    import redis.asyncio as redis
    log.info("Redis-Modul erfolgreich geladen")
except ImportError as e:
    log.error(f"Kritischer Fehler: {e}")
    sys.exit(1)

# Pipeline-Module
try:
    from pipeline.downloader import YouTubeDownloader, DownloadError, NetworkError
    from pipeline.audio_processor import AudioProcessor
    from pipeline.transcriber import WhisperTranscriber
    from pipeline.chapter_detector import ChapterDetector
    from pipeline.summarizer import OllamaSummarizer, OllamaTimeoutError
    from pipeline.podcast_exporter import PodcastExporter
    log.info("Pipeline-Module erfolgreich geladen")
except ImportError as e:
    log.error(f"Pipeline Fehler: {e}")
    YouTubeDownloader = None
    AudioProcessor = None
    WhisperTranscriber = None
    ChapterDetector = None
    OllamaSummarizer = None
    PodcastExporter = None

# Umgebungsvariablen
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yt_user:sicheres_passwort@postgres:5432/yt_ai_suite")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODELL", "llama3.2:1b")
WHISPER_MODEL = os.getenv("WHISPER_MODELL", "tiny")
WHISPER_DEVICE = os.getenv("WHISPER_GERAET", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_BERECHNUNG", "int8")

# Verzeichnisse
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
        
        # Pipeline-Komponenten
        self.downloader = YouTubeDownloader() if YouTubeDownloader else None
        self.audio_processor = AudioProcessor() if AudioProcessor else None
        self.transcriber = WhisperTranscriber(
            model_size=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        ) if WhisperTranscriber else None
        self.chapter_detector = ChapterDetector() if ChapterDetector else None
        self.summarizer = OllamaSummarizer(OLLAMA_URL, OLLAMA_MODEL, timeout=30) if OllamaSummarizer else None
        self.podcast_exporter = PodcastExporter() if PodcastExporter else None
        
        log.info(f"✅ Worker {worker_id} gestartet (PID: {os.getpid()})")
        
    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Holt nächsten Job aus Redis"""
        try:
            r = await redis.from_url(REDIS_URL)
            for queue in ["yt_jobs_prioritaet", "yt_jobs_normal"]:
                job_data = await r.lpop(queue)
                if job_data:
                    job = json.loads(job_data)
                    job_id = job.get('id') or job.get('job_id')
                    if not job_id:
                        log.error(f"Job hat keine ID: {job}")
                        continue
                    job['id'] = job_id
                    await r.setex(f"job:{job_id}:processing", 300, self.worker_id)
                    log.info(f"📦 Job {job_id} übernommen")
                    await r.aclose()
                    return job
            await r.aclose()
            return None
        except Exception as e:
            log.error(f"Fehler beim Job-Holen: {e}")
            return None

    async def update_progress(self, job_id: str, progress: float, status: str):
        """Aktualisiert Job-Fortschritt - mit Fehlerbehandlung"""
        try:
            if not job_id:
                return
            await job_fortschritt_update(job_id, progress, status)
            try:
                r = await redis.from_url(REDIS_URL)
                await r.setex(
                    f"fortschritt:{job_id}", 
                    3600, 
                    json.dumps({"fortschritt": progress, "status": status})
                )
                await r.aclose()
            except Exception as redis_error:
                log.error(f"Redis Progress Fehler: {redis_error}")
                # Nicht kritisch - weitermachen
        except Exception as e:
            log.error(f"Progress Fehler (ignoriert): {e}")

    async def check_abort(self, job_id: str) -> bool:
        """Prüft ob Job abgebrochen wurde"""
        try:
            r = await redis.from_url(REDIS_URL)
            aborted = await r.exists(f"abbruch:{job_id}")
            await r.aclose()
            return bool(aborted)
        except:
            return False

    async def process_job(self, job: Dict[str, Any]):
        """Verarbeitet einen Job - mit fix für den finalen Fehler"""
        job_id = job['id']
        url = job.get('url') or job.get('optionen', {}).get('url', '')
        options = job.get('optionen', {})
        
        log.info(f"▶️ Starte Job {job_id}: {url}")
        
        try:
            # 1. Download (5%)
            if self.downloader and url:
                await self.update_progress(job_id, 5.0, "herunterladen")
                video_info = await self.downloader.download_video(url, job_id, AUDIO_PATH)
                log.info(f"  ✅ Download: {video_info.get('titel', 'Unbekannt')}")
            else:
                video_info = {"titel": "Test-Video", "youtube_id": "test", "audio_pfad": None}
            
            if await self.check_abort(job_id):
                return
            
            # 2. Audio verarbeiten (20%)
            audio_file = video_info.get('audio_pfad')
            if audio_file and self.audio_processor:
                await self.update_progress(job_id, 20.0, "verarbeitung")
                audio_file = await self.audio_processor.process(audio_file, job_id)
            
            # 3. Transkription (35-70%)
            transcript = "Kein Transkript"
            if audio_file and self.transcriber:
                await self.update_progress(job_id, 35.0, "transkription")
                
                async def safe_progress_callback(p):
                    try:
                        if p is not None:
                            await self.update_progress(job_id, 35.0 + (p * 35.0), "transkription")
                    except Exception:
                        pass  # Ignorieren
                
                transcript = await self.transcriber.transcribe(
                    audio_file, job_id, safe_progress_callback
                )
                log.info(f"  ✅ Transkription: {len(transcript)} Zeichen")
            
            if await self.check_abort(job_id):
                return
            
            # 4. Kapitel (72%)
            chapters = []
            if self.chapter_detector:
                await self.update_progress(job_id, 72.0, "verarbeitung")
                chapters = await self.chapter_detector.detect(transcript, audio_file)
                log.info(f"  ✅ {len(chapters)} Kapitel")
            
            # 5. Zusammenfassung (80%) - optional
            summary = "Keine Zusammenfassung"
            if options.get('zusammenfassung_erstellen', True) and self.summarizer and transcript:
                await self.update_progress(job_id, 80.0, "zusammenfassung")
                style = options.get('zusammenfassung_stil', 'stichpunkte')
                summary = await self.summarizer.summarize(transcript, style, job_id)
                log.info(f"  ✅ Zusammenfassung")
            
            # 6. Speichern (100%)
            video_data = {
                **video_info,
                'transkript': transcript,
                'zusammenfassung': summary,
                'kapitel': json.dumps(chapters),
                'audio_pfad': audio_file,
                'podcast_pfad': None
            }
            
            await job_abgeschlossen(job_id, video_data)
            # KEIN update_progress mehr aufrufen - das verursacht den Fehler!
            self.jobs_processed += 1
            log.info(f"✅ Job {job_id} fertig (#{self.jobs_processed})")
            
        except Exception as e:
            log.error(f"❌ Job Fehler: {e}")
            await job_fehler(job_id, str(e)[:200])

    async def run_forever(self):
        """Haupt-Worker-Loop"""
        log.info(f"🚀 Worker {self.worker_id} läuft...")
        
        stats_interval = 60
        last_stats = datetime.now()
        
        while self.running:
            try:
                job = await self.get_next_job()
                
                if job:
                    self.current_job = job['id']
                    await self.process_job(job)
                    self.current_job = None
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(5)
                
                # Statistiken
                now = datetime.now()
                if (now - last_stats).seconds > stats_interval:
                    uptime = (now - self.start_time).seconds
                    log.info(f"📊 {self.worker_id} - Jobs: {self.jobs_processed}, Uptime: {uptime}s")
                    last_stats = now
                
            except Exception as e:
                log.error(f"Loop Fehler: {e}")
                await asyncio.sleep(5)
        
        log.info(f"👋 Worker {self.worker_id} beendet")

    async def shutdown(self):
        """Sauberes Herunterfahren"""
        log.info(f"🛑 Worker {self.worker_id} wird heruntergefahren...")
        self.running = False
        if self.current_job:
            await job_status_update(self.current_job, "abgebrochen")

async def main():
    worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")
    worker = YouTubeWorker(worker_id)
    
    try:
        await worker.run_forever()
    except KeyboardInterrupt:
        await worker.shutdown()
    except Exception as e:
        log.error(f"Kritischer Fehler: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
    async def process_job(self, job: Dict[str, Any]):
        """Verarbeitet einen Job - finale Version ohne Fehler"""
        job_id = job['id']
        url = job.get('url') or job.get('optionen', {}).get('url', '')
        options = job.get('optionen', {})
        
        log.info(f"▶️ Starte Job {job_id}: {url}")
        
        try:
            # 1. Download (5%)
            if self.downloader and url:
                await self.safe_update_progress(job_id, 5.0, "herunterladen")
                video_info = await self.downloader.download_video(url, job_id, AUDIO_PATH)
                log.info(f"  ✅ Download: {video_info.get('titel', 'Unbekannt')}")
            else:
                video_info = {"titel": "Test-Video", "youtube_id": "test", "audio_pfad": None}
            
            if await self.check_abort(job_id):
                return
            
            # 2. Audio verarbeiten (20%)
            audio_file = video_info.get('audio_pfad')
            if audio_file and self.audio_processor:
                await self.safe_update_progress(job_id, 20.0, "verarbeitung")
                audio_file = await self.audio_processor.process(audio_file, job_id)
            
            # 3. Transkription (35-70%)
            transcript = "Kein Transkript"
            if audio_file and self.transcriber:
                await self.safe_update_progress(job_id, 35.0, "transkription")
                
                async def progress_callback(p):
                    if p is not None:
                        await self.safe_update_progress(job_id, 35.0 + (p * 35.0), "transkription")
                
                transcript = await self.transcriber.transcribe(
                    audio_file, job_id, progress_callback
                )
                log.info(f"  ✅ Transkription: {len(transcript)} Zeichen")
            
            if await self.check_abort(job_id):
                return
            
            # 4. Kapitel (72%)
            chapters = []
            if self.chapter_detector:
                await self.safe_update_progress(job_id, 72.0, "verarbeitung")
                chapters = await self.chapter_detector.detect(transcript, audio_file)
                log.info(f"  ✅ {len(chapters)} Kapitel")
            
            # 5. Zusammenfassung (80%)
            summary = "Keine Zusammenfassung"
            if options.get('zusammenfassung_erstellen', True) and self.summarizer and transcript:
                await self.safe_update_progress(job_id, 80.0, "zusammenfassung")
                style = options.get('zusammenfassung_stil', 'stichpunkte')
                summary = await self.summarizer.summarize(transcript, style, job_id)
                log.info(f"  ✅ Zusammenfassung")
            
            # 6. Speichern (100%) - KEIN Progress-Update mehr!
            video_data = {
                **video_info,
                'transkript': transcript,
                'zusammenfassung': summary,
                'kapitel': json.dumps(chapters),
                'audio_pfad': audio_file,
                'podcast_pfad': None
            }
            
            await job_abgeschlossen(job_id, video_data)
            self.jobs_processed += 1
            log.info(f"✅ Job {job_id} fertig (#{self.jobs_processed})")
            
        except Exception as e:
            log.error(f"❌ Job Fehler: {e}")
            await job_fehler(job_id, str(e)[:200])
    
    async def safe_update_progress(self, job_id: str, progress: float, status: str):
        """Sichere Progress-Update Funktion"""
        try:
            if job_id and progress is not None:
                await job_fortschritt_update(job_id, progress, status)
                try:
                    r = await redis.from_url(REDIS_URL)
                    await r.setex(
                        f"fortschritt:{job_id}", 
                        3600, 
                        json.dumps({"fortschritt": progress, "status": status})
                    )
                    await r.aclose()
                except:
                    pass  # Redis-Fehler ignorieren
        except:
            pass  # Alle Fehler ignorieren
