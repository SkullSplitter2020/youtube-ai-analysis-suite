#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Chapter Detector
Erkennung von Kapiteln basierend auf Pausen und Themen
"""

import json
import logging
import re

log = logging.getLogger("chapter_detector")

class ChapterDetector:
    def __init__(self):
        pass
    
    async def detect(self, transcript: str, audio_file: str = None) -> list:
        """
        Erkennt Kapitel im Transkript
        """
        try:
            # Einfache Kapitelerkennung basierend auf Text-Struktur
            chapters = []
            
            # Nach Überschriften suchen (z.B. "Kapitel 1:", "Teil 1:", etc.)
            lines = transcript.split('\n')
            current_chapter = {"start": 0, "title": "Einleitung", "text": []}
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Nach Kapitel-Überschriften suchen
                if re.match(r'^(Kapitel|Teil|Abschnitt|Chapter|Part)\s+\d+[:.]', line, re.IGNORECASE):
                    # Vorheriges Kapitel speichern
                    if current_chapter["text"]:
                        current_chapter["text"] = ' '.join(current_chapter["text"])
                        chapters.append(current_chapter.copy())
                    
                    # Neues Kapitel beginnen
                    current_chapter = {
                        "start": i,
                        "title": line,
                        "text": []
                    }
                else:
                    if line:  # Nur nicht-leere Zeilen
                        current_chapter["text"].append(line)
            
            # Letztes Kapitel speichern
            if current_chapter["text"]:
                current_chapter["text"] = ' '.join(current_chapter["text"])
                chapters.append(current_chapter)
            
            # Wenn keine Kapitel gefunden, ein Kapitel erstellen
            if len(chapters) <= 1:
                chapters = [{
                    "start": 0,
                    "title": "Vollständiges Video",
                    "text": transcript[:500] + "..."
                }]
            
            log.info(f"{len(chapters)} Kapitel erkannt")
            return chapters
            
        except Exception as e:
            log.error(f"Fehler bei Kapitelerkennung: {e}")
            return [{"start": 0, "title": "Kapitel 1", "text": transcript[:200] + "..."}]