import yt_dlp, os, logging
log = logging.getLogger("downloader")


def video_herunterladen(job_id, optionen):
    verz = os.path.join("/app/data/audio", job_id)
    os.makedirs(verz, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(verz, "%(id)s.%(ext)s"),
        "quiet": True, "no_warnings": True, "geo_bypass": True,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "wav", "preferredquality": "192"}],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(optionen.get("url", ""), download=True)
        pfad = os.path.join(verz, f"{info.get('id', 'x')}.wav")
        log.info(f"Heruntergeladen: {info.get('title')}")
        return info, pfad
