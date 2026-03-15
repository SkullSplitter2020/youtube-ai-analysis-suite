import logging
log = logging.getLogger("kapitel")


def _ts(sek):
    h, m, s = int(sek // 3600), int((sek % 3600) // 60), int(sek % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def kapitel_erkennen(segmente, transkript):
    if not segmente:
        return [{"zeitstempel": "00:00", "sekunden": 0.0, "titel": "Einleitung"}]
    kapitel, aktuell, ende = [], [], 0.0
    for i, s in enumerate(segmente):
        bruch = (s["start"] - ende > 3.0 or
                 (i > 0 and i % 25 == 0 and s["start"] - segmente[0]["start"] > 60))
        if bruch and aktuell:
            st = aktuell[0]["start"]
            txt = " ".join(x["text"] for x in aktuell[:3]).split()[:6]
            kapitel.append({"zeitstempel": _ts(st), "sekunden": st,
                           "titel": " ".join(txt) if txt else f"Kapitel {len(kapitel)+1}"})
            aktuell = []
        aktuell.append(s)
        ende = s["end"]
    if aktuell:
        st = aktuell[0]["start"]
        txt = " ".join(x["text"] for x in aktuell[:3]).split()[:6]
        kapitel.append({"zeitstempel": _ts(st), "sekunden": st,
                       "titel": " ".join(txt) if txt else f"Kapitel {len(kapitel)+1}"})
    log.info(f"{len(kapitel)} Kapitel")
    return kapitel or [{"zeitstempel": "00:00", "sekunden": 0.0, "titel": "Einleitung"}]
