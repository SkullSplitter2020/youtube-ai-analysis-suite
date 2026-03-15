#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Worker
Haupt-Worker-Prozess für die Video-Verarbeitung
"""

import os
import sys
import json
import asyncio
import logging
import signal
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Umgebungsvariablen laden
load_dotenv()

# Logging Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("worker")

# Health-Checks nur importieren wenn aktiviert
HEALTH_ENABLED = os.getenv("ENABLE_HEALTH_CHECKS", "false").lower() == "true"
if HEALTH_ENABLED:
    try:
        from health import WorkerHealthCheck, heartbeat_worker
        log.info("Health-Checks erfolgreich geladen")
    except ImportError as e:
        log.warning(f"Health-Checks konnten nicht geladen werden: {e}")
        HEALTH_ENABLED = False

# Datenbank-Importe
try:
    from db_worker import (
        job_abgeschlossen, job_fehler, job_status_update,
        job_fortschritt_update, job_abbrechen_pruefen
    )
    log.info("Datenbank-Module erfolgreich geladen")
except ImportError as e:
    log.error(f"Kritischer Fehler: Datenbank-Module nicht gefunden: {e}")
    sys.exit(1)

# Pipeline-Importe
try:
    from pipeline import (
        YouTubeDownloader, DownloadError, NetworkError,
        AudioProcessor,
        WhisperTranscriber,
        ChapterDetector,
        OllamaSummarizer, OllamaTimeoutError,
        PodcastExporter
    )
    log.info("Pipeline-Module erfolgreich geladen")
except ImportError as e:
    log.error(f"Kritischer Fehler: Pipeline-Module nicht gefunden: {e}")
    sys.exit(1)

# Redis für Queue
try:
    import redis.asyncio as redis
    log.info("Redis-Modul erfolgreich geladen")
except ImportError as e:
    log.error(f"Kritischer Fehler: Redis-Modul nicht gefunden: {e}")
    sys.exit(1)

# Umgebungsvariablen
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yt_user:pass@postgres:5432/yt_ai_suite")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODELL", "llama3")
WHISPER_MODEL = os.getenv("WHISPER_MODELL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_GERAET", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_BERECHNUNG", "int8")

# Verzeichnisse
AUDIO_PATH = "/app/data/audio"
TRANSCRIPTS_PATH = "/app/data/transcripts"
SUMMARIES_PATH = "/app/data/summaries"
CHAPTERS_PATH = "/app/data/chapters"
PODCASTS_PATH = "/app/data/podcasts"

# Verzeichnisse erstellen
for path in [AUDIO_PATH, TRANSCRIPTS_PATH, SUMMARIES_PATH, CHAPTERS_PATH, PODCASTS_PATH]:
    os.makedirs(path, exist_ok=True)

class YouTubeWorker:
    """Haupt-Worker-Klasse für die Video-Verarbeitung"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.running = True
        self.current_job = None
        self.health_check = None
        
        # Pipeline-Komponenten
        self.downloader = YouTubeDownloader(
            max_retries=int(os.getenv("DOWNLOAD_MAX_RETRIES", "3")),
            initial_wait=int(os.getenv("DOWNLOAD_INITIAL_WAIT", "1")),
            max_wait=int(os.getenv("DOWNLOAD_MAX_WAIT", "10"))
        )
        self.audio_processor = AudioProcessor()
        self.transcriber = WhisperTranscriber(
            model_size=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        )
        self.chapter_detector = ChapterDetector()
        self.summarizer = OllamaSummarizer(
            ollama_url=OLLAMA_URL,
            model=OLLAMA_MODEL,
            timeout=int(os.getenv("OLLAMA_TIMEOUT", "60"))
        )
        self.podcast_exporter = PodcastExporter()
        
        log.info(f"Worker {worker_id} initialisiert")
        
    async def setup_health_checks(self):
        """Health-Checks einrichten"""
        if HEALTH_ENABLED:
            try:
                self.health_check = WorkerHealthCheck(
                    worker_id=self.worker_id,
                    redis_url=REDIS_URL,
                    postgres_url=DATABASE_URL
                )
                
                # Health-Check Server starten
                port = int(os.getenv("HEALTH_CHECK_PORT", "8081"))
                asyncio.create_task(self.health_check.start_health_server(port))
                
                # Heartbeat starten
                interval = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "30"))
                asyncio.create_task(heartbeat_worker(self.worker_id, REDIS_URL, interval))
                
                log.info(f"Health-Checks gestartet (Port {port}, Heartbeat {interval}s)")
            except Exception as e:
                log.error(f"Fehler beim Starten der Health-Checks: {e}")
    
async def get_next_job(self) -> Optional[Dict[str, Any]]:
    """Holt nächsten Job aus der Redis Queue"""
    try:
        r = await redis.from_url(REDIS_URL)
        
        # Prioritäts-Queue zuerst prüfen
        for queue in ["yt_jobs_prioritaet", "yt_jobs_normal"]:
            job_data = await r.lpop(queue)
            if job_data:
                job = json.loads(job_data)
                
                # Prüfen ob 'id' vorhanden ist
                if 'id' not in job:
                    log.error(f"Job in Queue hat keine ID: {job}")
                    continue
                
                # Job in Redis als "in Bearbeitung" markieren
                await r.setex(f"job:{job['id']}:processing", 300, self.worker_id)
                
                log.info(f"Job {job['id']} aus Queue '{queue}' übernommen")
                await r.aclose()
                return job
                
        await r.aclose()
        return None
        
    except Exception as e:
        log.error(f"Fehler beim Holen des nächsten Jobs: {e}")
        return None    
    async def check_abort(self, job_id: str) -> bool:
        """Prüft ob Job abgebrochen werden soll"""
        try:
            r = await redis.from_url(REDIS_URL)
            aborted = await r.exists(f"abbruch:{job_id}")
            await r.aclose()
            
            if aborted:
                log.info(f"Job {job_id} wurde abgebrochen")
                await job_status_update(job_id, "abgebrochen")
                
            return bool(aborted)
            
        except Exception as e:
            log.error(f"Fehler beim Prüfen des Abbruchs für Job {job_id}: {e}")
            return False
    
    async def process_job(self, job: Dict[str, Any]):
        """Verarbeitet einen einzelnen Job"""
        job_id = job['id']
        url = job['url']
        options = job.get('optionen', {})
        
        log.info(f"Starte Verarbeitung von Job {job_id}: {url}")
        
        try:
            # 1. Video downloaden (5%)
            await self.update_progress(job_id, 5.0, "herunterladen")
            video_info = await self.downloader.download_video(
                url=url,
                job_id=job_id,
                output_path=AUDIO_PATH
            )
            
            if await self.check_abort(job_id):
                return
            
            # 2. Audio verarbeiten (20%)
            await self.update_progress(job_id, 20.0, "verarbeitung")
            audio_file = video_info.get('audio_pfad')
            if audio_file:
                processed_audio = await self.audio_processor.process(
                    audio_file,
                    job_id
                )
            else:
                processed_audio = None
            
            if await self.check_abort(job_id):
                return
            
            # 3. Transkription (35-70%)
            await self.update_progress(job_id, 35.0, "transkription")
            if processed_audio:
                transcript = await self.transcriber.transcribe(
                    audio_file=processed_audio,
                    job_id=job_id,
                    progress_callback=lambda p: self.update_progress(
                        job_id, 
                        35.0 + (p * 0.35),
                        "transkription"
                    )
                )
            else:
                transcript = "Kein Audio verfügbar"
            
            if await self.check_abort(job_id):
                return
            
            # 4. Kapitel erkennen (72%)
            await self.update_progress(job_id, 72.0, "verarbeitung")
            chapters = await self.chapter_detector.detect(
                transcript=transcript,
                audio_file=processed_audio
            )
            
            if await self.check_abort(job_id):
                return
            
            # 5. Zusammenfassung (80%)
            await self.update_progress(job_id, 80.0, "zusammenfassung")
            summary_style = options.get('summary_style', 'stichpunkte')
            try:
                summary = await self.summarizer.summarize(
                    text=transcript,
                    style=summary_style,
                    job_id=job_id
                )
            except OllamaTimeoutError:
                log.warning(f"Timeout bei Zusammenfassung für Job {job_id}")
                summary = "⚠️ Zusammenfassung fehlgeschlagen (Timeout)"
            
            if await self.check_abort(job_id):
                return
            
            # 6. Podcast exportieren (95%) - optional
            podcast_file = None
            if options.get('export_podcast', False) and processed_audio:
                await self.update_progress(job_id, 95.0, "verarbeitung")
                podcast_file = await self.podcast_exporter.export(
                    audio_file=processed_audio,
                    chapters=chapters,
                    job_id=job_id,
                    output_path=PODCASTS_PATH
                )
            
            # 7. Alles speichern (100%)
            video_data = {
                **video_info,
                'transkript': transcript,
                'zusammenfassung': summary,
                'kapitel': json.dumps(chapters),
                'audio_pfad': processed_audio,
                'podcast_pfad': podcast_file
            }
            
            await job_abgeschlossen(job_id, video_data)
            await self.update_progress(job_id, 100.0, "abgeschlossen")
            
            log.info(f"Job {job_id} erfolgreich abgeschlossen")
            
        except NetworkError as e:
            log.error(f"Netzwerkfehler bei Job {job_id}: {e}")
            await job_fehler(job_id, f"Netzwerkfehler: {str(e)}")
            
        except DownloadError as e:
            log.error(f"Download-Fehler bei Job {job_id}: {e}")
            await job_fehler(job_id, f"Download-Fehler: {str(e)}")
            
        except Exception as e:
            log.error(f"Unerwarteter Fehler bei Job {job_id}: {e}")
            await job_fehler(job_id, f"Unerwarteter Fehler: {str(e)}")
            
        finally:
            # Aufräumen
            if self.health_check:
                self.health_check.current_job = None
                self.health_check.last_heartbeat = datetime.now()
    
    async def run(self):
        """Haupt-Worker-Loop"""
        log.info(f"Worker {self.worker_id} gestartet")
        
        # Signal-Handler für sauberes Beenden
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        # Health-Checks einrichten
        await self.setup_health_checks()
        
        # Haupt-Loop
        while self.running:
            try:
                # Nächsten Job holen
                job = await self.get_next_job()
                
                if job:
                    # Job verarbeiten
                    await self.process_job(job)
                    
                    # Kurze Pause zwischen Jobs
                    await asyncio.sleep(1)
                else:
                    # Keine Jobs - warten
                    await asyncio.sleep(2)
                    
            except Exception as e:
                log.error(f"Fehler in Worker-Loop: {e}")
                await asyncio.sleep(5)
        
        log.info(f"Worker {self.worker_id} beendet")
    
    async def shutdown(self):
        """Sauberes Herunterfahren"""
        log.info(f"Worker {self.worker_id} wird heruntergefahren...")
        self.running = False
        
        if self.current_job:
            log.info(f"Aktuellen Job {self.current_job} abbrechen...")
            # Job als abgebrochen markieren
            await job_status_update(self.current_job, "abgebrochen")

    async def main():
        """Hauptfunktion"""
        # Worker-ID erstellen
        worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")
        
        # Worker erstellen und starten
        worker = YouTubeWorker(worker_id)
        
        try:
            await worker.run()
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt empfangen")
            await worker.shutdown()
        except Exception as e:
            log.error(f"Kritischer Fehler: {e}")
            sys.exit(1)

    if __name__ == "__main__":
        asyncio.run(main())