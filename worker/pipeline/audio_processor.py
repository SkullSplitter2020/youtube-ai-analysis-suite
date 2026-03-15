import subprocess, logging
log = logging.getLogger("audio")


def audio_verarbeiten(eingabe, job_id):
    ausgabe = eingabe.replace(".wav", "_v.wav")
    r = subprocess.run(["ffmpeg", "-y", "-i", eingabe, "-ar", "16000",
                        "-ac", "1", "-af", "loudnorm", ausgabe],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log.warning(f"FFmpeg Warnung: {r.stderr[:200]}")
        return eingabe
    return ausgabe
