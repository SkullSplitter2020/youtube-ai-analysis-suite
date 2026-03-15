#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Downloader
Video-Download mit yt-dlp und Retry-Logik
"""

import os
import logging
import asyncio
import yt_dlp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger("downloader")

class DownloadError(Exception):
    pass

class NetworkError(DownloadError):
    pass

class YouTubeDownloader:
    def __init__(self, max_retries=3, initial_wait=1, max_wait=10):
        self.max_retries = max_retries
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(NetworkError),
        before_sleep=lambda retry_state: log.warning(
            f"Download fehlgeschlagen (Versuch {retry_state.attempt_number}/3). "
            f"Nächster Versuch in {retry_state.next_action.sleep} Sekunden..."
        )
    )
    async def download_video(self, url: str, job_id: str, output_path: str) -> dict:
        """
        Lädt Video herunter mit automatischen Retries bei Netzwerkfehlern
        """
        # Job-Verzeichnis erstellen
        job_dir = os.path.join(output_path, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(job_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': False,
            'extractor_retries': 3,
            'file_access_retries': 3,
        }
        
        try:
            # Info extrahieren
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Info mit Retry extrahieren
                info = await self._extract_info_with_retry(ydl, url)
                
                # Video downloaden
                ydl.download([url])
                
                # Audio-Datei finden
                audio_file = None
                for file in os.listdir(job_dir):
                    if file.endswith('.wav'):
                        audio_file = os.path.join(job_dir, file)
                        break
                
                return {
                    'youtube_id': info.get('id', ''),
                    'titel': info.get('title', 'Unbekannter Titel'),
                    'beschreibung': info.get('description', ''),
                    'kanal': info.get('uploader', ''),
                    'dauer': info.get('duration', 0),
                    'hochladedatum': info.get('upload_date', ''),
                    'thumbnail_url': info.get('thumbnail', ''),
                    'audio_pfad': audio_file
                }
                
        except yt_dlp.utils.DownloadError as e:
            if any(network_error in str(e).lower() for network_error in 
                   ['network', 'connection', 'timeout', 'http error 403', 'unreachable']):
                raise NetworkError(f"Netzwerkfehler beim Download: {e}") from e
            raise DownloadError(f"Download fehlgeschlagen: {e}") from e
        except Exception as e:
            raise DownloadError(f"Unerwarteter Fehler: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(NetworkError)
    )
    async def _extract_info_with_retry(self, ydl, url: str) -> dict:
        """
        Extrahiert Video-Info mit Retry-Logik
        """
        try:
            # In Threadpool ausführen da yt-dlp synchron ist
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        except Exception as e:
            if 'network' in str(e).lower():
                raise NetworkError(f"Info-Extraktion fehlgeschlagen: {e}") from e
            raise