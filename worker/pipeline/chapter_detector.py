#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Chapter Detector
Erkennung von Kapiteln basierend auf Pausen und Themen
"""

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
            
            # Text in Absätze aufteilen
            paragraphs = transcript.split('\n\n')
            
            for i, para in enumerate(paragraphs):
                if len(para) > 100:  # Nur längere Absätze als Kapitel
                    # Ersten Satz als Titel
                    first_sentence = para.split('.')[0][:50]
                    
                    chapters.append({
                        "start": i * 60,  # Ungefähre Zeit in Sekunden
                        "title": first_sentence,
                        "text": para[:200] + "..."
                    })
            
            # Wenn keine Kapitel gefunden, ein Kapitel erstellen
            if len(chapters) <= 1:
                chapters = [{
                    "start": 0,
                    "title": "Vollständiges Video",
                    "text": transcript[:500] + "..."
                }]
            
            log.info(f"{len(chapters)} Kapitel erkannt")
            return chapters[:10]  # Maximal 10 Kapitel
            
        except Exception as e:
            log.error(f"Fehler bei Kapitelerkennung: {e}")
            return [{"start": 0, "title": "Kapitel 1", "text": transcript[:200] + "..."}]