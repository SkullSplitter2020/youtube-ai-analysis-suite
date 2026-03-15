from faster_whisper import WhisperModel
import os, logging
from typing import Optional, Callable

log = logging.getLogger("transcriber")
_cache = {}


def _modell(groesse):
    g = os.getenv("WHISPER_GERAET", "cpu")
    b = os.getenv("WHISPER_BERECHNUNG", "int8")
    k = f"{groesse}_{g}_{b}"
    if k not in _cache:
        log.info(f"Lade Whisper {groesse} ({g}/{b})")
        _cache[k] = WhisperModel(groesse, device=g, compute_type=b)
    return _cache[k]


def audio_transkribieren(
    pfad: str,
    modell: str = "base",
    sprache: Optional[str] = None,
    abbruch_callback: Optional[Callable] = None  # ← NEU
):
    w = _modell(modell)
    segs_iter, info = w.transcribe(
        pfad,
        language=sprache,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        word_timestamps=True
    )
    log.info(f"Sprache: {info.language} ({info.language_probability:.0%})")

    segmente, teile = [], []
    for i, s in enumerate(segs_iter):

        # Alle 10 Segmente auf Abbruch prüfen
        if abbruch_callback and i % 10 == 0 and abbruch_callback():
            log.info(f"Transkription nach {i} Segmenten abgebrochen")
            # Teilergebnis zurückgeben
            text = " ".join(teile)
            return text, segmente

        segmente.append({
            "start": round(s.start, 2),
            "end":   round(s.end, 2),
            "text":  s.text.strip()
        })
        teile.append(s.text.strip())

    text = " ".join(teile)
    log.info(f"{len(segmente)} Segmente, {len(text)} Zeichen")
    return text, segmente