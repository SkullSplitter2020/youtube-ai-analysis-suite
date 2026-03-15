#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - Summarizer
KI-Zusammenfassung mit Ollama
"""

import logging
import asyncio
import aiohttp
import json

log = logging.getLogger("summarizer")

class OllamaTimeoutError(Exception):
    pass

class OllamaSummarizer:
    def __init__(self, ollama_url: str, model: str, timeout: int = 60):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout
        
    async def summarize(self, text: str, style: str, job_id: str) -> str:
        """
        Erstellt Zusammenfassung mit Timeout
        """
        try:
            # Text kürzen wenn zu lang
            if len(text) > 10000:
                text = text[:10000] + "..."
            
            prompt = self._create_prompt(text, style)
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with asyncio.timeout(self.timeout):
                        payload = {
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.7,
                                "num_predict": 1000
                            }
                        }
                        
                        async with session.post(
                            f"{self.ollama_url}/api/generate",
                            json=payload
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                summary = result.get("response", "")
                                
                                # Zusammenfassung speichern
                                summary_file = f"/app/data/summaries/{job_id}.txt"
                                os.makedirs(os.path.dirname(summary_file), exist_ok=True)
                                
                                with open(summary_file, 'w', encoding='utf-8') as f:
                                    f.write(summary)
                                
                                return summary
                            else:
                                error_text = await response.text()
                                log.error(f"Ollama HTTP {response.status}: {error_text}")
                                return "⚠️ Zusammenfassung fehlgeschlagen"
                                
                except asyncio.TimeoutError:
                    log.error(f"Ollama Timeout nach {self.timeout}s für Job {job_id}")
                    return "⚠️ Zusammenfassung fehlgeschlagen (Timeout)"
                    
        except Exception as e:
            log.error(f"Fehler bei Zusammenfassung: {e}")
            return f"⚠️ Zusammenfassung fehlgeschlagen: {str(e)[:100]}"
    
    def _create_prompt(self, text: str, style: str) -> str:
        """
        Erstellt Prompt basierend auf gewähltem Stil
        """
        prompts = {
            "stichpunkte": f"Fasse folgenden Text in Stichpunkten zusammen:\n\n{text}",
            "ausführlich": f"Erstelle eine ausführliche Zusammenfassung:\n\n{text}",
            "kernaussagen": f"Extrahiere die 5-7 wichtigsten Kernaussagen:\n\n{text}",
            "podcast": f"Schreibe ein Podcast-Skript basierend auf:\n\n{text}"
        }
        return prompts.get(style, prompts["stichpunkte"])