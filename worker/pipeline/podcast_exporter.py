import subprocess
import os
import logging

log = logging.getLogger("podcast")


def podcast_exportieren(audio, segmente, kapitel, info, job_id):
    verz = "/app/data/podcasts"
    os.makedirs(verz, exist_ok=True)
    vid = info.get("id", job_id)
    aus = os.path.join(verz, f"{vid}_podcast.mp3")
    meta = os.path.join(verz, f"{vid}_meta.txt")

    zeilen = [
        ";FFMETADATA1",
        f"title={info.get('title', 'Podcast')}",
        f"artist={info.get('uploader', 'AI Suite')}",
        ""
    ]
    for i, k in enumerate(kapitel):
        s = int(k.get("sekunden", 0) * 1000)
        if i + 1 < len(kapitel):
            e = int(kapitel[i + 1]["sekunden"] * 1000)
        else:
            e = s + 600000
        zeilen += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={s}",
            f"END={e}",
            f"title={k.get('titel', '')}",
            ""
        ]

    with open(meta, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen))

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", audio, "-i", meta, "-map_metadata", "1",
         "-codec:a", "libmp3lame", "-b:a", "128k", "-id3v2_version", "3", aus],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        log.warning(f"Podcast mit Metadaten fehlgeschlagen, versuche ohne...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio,
             "-codec:a", "libmp3lame", "-b:a", "128k", aus],
            check=True
        )

    log.info(f"Podcast exportiert: {aus}")
    return aus