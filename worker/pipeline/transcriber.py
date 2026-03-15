#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Transcriber
Transkription mit Faster-Whisper
"""

import os
import logging
import asyncio
from faster_whisper import WhisperModel

log = logging.getLogger("transcriber")

class WhisperTranscriber:
    def __init__(self, model_size="tiny", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
    def _load_model(self):
        """Lädt das Whisper-Modell"""
        if not self.model:
            log.info(f"Lade Whisper-Modell: {self.model_size} ({self.device}, {self.compute_type})")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self.model
    
    async def transcribe(self, audio_file: str, job_id: str, progress_callback=None):
        """
        Transkribiert Audio-Datei
        """
        try:
            model = self._load_model()
            
            # Transkription in Threadpool ausführen
            loop = asyncio.get_event_loop()
            
            def _transcribe():
                segments, info = model.transcribe(
                    audio_file,
                    beam_size=5,
                    language="de",
                    task="transcribe",
                    vad_filter=True,
                    vad_parameters=dict(
                        threshold=0.5,
                        min_speech_duration_ms=250,
                        min_silence_duration_ms=2000
                    )
                )
                
                # Segmente sammeln
                text_parts = []
                
                for i, segment in enumerate(segments):
                    text_parts.append(segment.text)
                    
                    # Fortschritt callback (alle 10 Segmente)
                    if progress_callback and i % 10 == 0:
                        progress = min(0.95, (i + 1) / 100)
                        loop.call_soon_threadsafe(
                            lambda p=progress: asyncio.create_task(progress_callback(p))
                        )
                
                return ' '.join(text_parts)
            
            transcript = await loop.run_in_executor(None, _transcribe)
            
            # Transkript speichern
            transcript_file = f"/app/data/transcripts/{job_id}.txt"
            os.makedirs(os.path.dirname(transcript_file), exist_ok=True)
            
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            log.info(f"Transkription abgeschlossen für Job {job_id}")
            return transcript
            
        except Exception as e:
            log.error(f"Fehler bei Transkription: {e}")
            raise