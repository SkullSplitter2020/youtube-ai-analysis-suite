#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Podcast Exporter
Exportiert Audio als Podcast mit Kapitelmarken
"""

import os
import logging
import subprocess
import json

log = logging.getLogger("podcast_exporter")

class PodcastExporter:
    def __init__(self):
        pass
    
    async def export(self, audio_file: str, chapters: list, job_id: str, output_path: str) -> str:
        """
        Exportiert Audio als Podcast mit Kapitelmarken
        """
        try:
            os.makedirs(output_path, exist_ok=True)
            
            # Output-Datei
            podcast_file = os.path.join(output_path, f"{job_id}.mp3")
            
            # Kapitel-Metadaten für FFmpeg
            metadata_file = os.path.join(output_path, f"{job_id}_chapters.txt")
            
            with open(metadata_file, 'w') as f:
                f.write(";FFMETADATA1\n")
                for i, chapter in enumerate(chapters):
                    start_time = i * 60  # Vereinfacht: 1 Minute pro Kapitel
                    end_time = (i + 1) * 60
                    
                    f.write("[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    f.write(f"START={start_time * 1000}\n")
                    f.write(f"END={end_time * 1000}\n")
                    f.write(f"title={chapter.get('title', f'Kapitel {i+1}')}\n")
            
            # FFmpeg mit Kapitel-Metadaten
            cmd = [
                'ffmpeg',
                '-i', audio_file,
                '-i', metadata_file,
                '-map_metadata', '1',
                '-codec', 'copy',
                '-y',
                podcast_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                log.error(f"FFmpeg Podcast Export Fehler: {stderr.decode()}")
                # Fallback: Einfach kopieren
                cmd = ['ffmpeg', '-i', audio_file, '-codec', 'copy', '-y', podcast_file]
                process = await asyncio.create_subprocess_exec(*cmd)
                await process.communicate()
            
            # Aufräumen
            if os.path.exists(metadata_file):
                os.remove(metadata_file)
            
            log.info(f"Podcast exportiert: {podcast_file}")
            return podcast_file
            
        except Exception as e:
            log.error(f"Fehler beim Podcast-Export: {e}")
            return audio_file  # Fallback: Original-Audio