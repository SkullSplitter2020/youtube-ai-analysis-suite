## 📋 Drei Dokumente für dein Projekt

---

## 1. 📄 `README.md`

```markdown
# 🎬 YouTube AI Analysis Suite

Eine vollständige, selbst gehostete KI-Plattform zur automatischen
Analyse von YouTube-Videos. Transkription, Zusammenfassung, Kapitel-
erkennung und KI-Chat – alles lokal auf deinem Server oder NAS.

---

## 🚀 Features

### Core Pipeline
- **Video-Download** via yt-dlp (Single + Playlist)
- **Audio-Extraktion** via FFmpeg (16kHz Mono, Lautstärke-Normalisierung)
- **Transkription** via Faster-Whisper (tiny/base/small/medium/large)
- **Kapitel-Erkennung** via Pause-Detection + Topic-Segmentierung
- **KI-Zusammenfassung** via Ollama (lokal) oder OpenAI API
- **Podcast-Export** als MP3 mit Kapitelmarken

### Dashboard
- Moderne Web-UI (Vanilla JS, Dark Mode)
- Echtzeit-Fortschrittsanzeige (5s Polling)
- Job-Verwaltung (Erstellen, Abbrechen, Löschen)
- Batch-Löschen (alle fehlerhaften/abgebrochenen Jobs)
- Volltextsuche in Transkripten + Zusammenfassungen
- KI-Chat über Video-Inhalte

### Export-Formate
- TXT (Transkript + Zusammenfassung)
- Markdown (strukturiert mit Kapiteln)
- JSON (komplette Daten)
- Podcast MP3 (mit Kapitelmarken)

### Zusammenfassungs-Stile
- Stichpunkte
- Ausführlich
- Kernaussagen (5-7 Punkte)
- Podcast-Skript

---

## 🏗️ Architektur

```
Browser (Port 3000)
    │
    ▼
Python HTTP-Server (Frontend)
    │
    ├── Static Files (HTML/CSS/JS)
    └── API-Proxy → FastAPI (Port 8000)
                        │
                ┌───────┴────────┐
                │                │
           PostgreSQL          Redis
           (Jobs/Videos)    (Queue/Progress)
                                 │
                        Worker Pool (×2)
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                 yt-dlp       Whisper      Ollama
               (Download)  (Transkript)  (Zusammenfassung)
```

### Services

| Service    | Technologie        | Port  | Funktion                    |
|------------|--------------------|-------|-----------------------------|
| frontend   | Python http.server | 3000  | Web-Dashboard               |
| api        | FastAPI            | 8000  | REST-API + WebSocket        |
| worker     | Python (×2)        | –     | Video-Verarbeitung          |
| postgres   | PostgreSQL 16      | 5432  | Persistente Datenspeicherung|
| redis      | Redis 7            | 6379  | Job-Queue + Fortschritt     |
| ollama     | Ollama             | 11434 | Lokales LLM                 |

---

## 📁 Projektstruktur

```
youtube-ai-suite/
├── docker-compose.yml
├── .env
├── .env.example
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py              # FastAPI App + CORS
│   ├── models.py            # SQLAlchemy Modelle
│   ├── schemas.py           # Pydantic Schemas
│   ├── database.py          # DB-Verbindung
│   ├── queue_manager.py     # Redis Queue
│   └── routers/
│       ├── jobs.py          # Job CRUD + WebSocket
│       ├── search.py        # Volltextsuche
│       ├── export.py        # TXT/MD/JSON/Podcast
│       └── chat.py          # KI-Chat
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── worker.py            # Haupt-Worker-Loop
│   ├── db_worker.py         # DB-Operationen
│   └── pipeline/
│       ├── downloader.py    # yt-dlp
│       ├── audio_processor.py # FFmpeg
│       ├── transcriber.py   # Faster-Whisper
│       ├── chapter_detector.py # Kapitel
│       ├── summarizer.py    # Ollama/OpenAI
│       └── podcast_exporter.py # MP3
├── frontend/
│   ├── Dockerfile
│   ├── server.py            # Python HTTP-Server
│   ├── index.html           # Dashboard HTML
│   ├── style.css            # Dark Theme CSS
│   └── app.js               # Vanilla JS Frontend
└── data/
    ├── audio/               # Heruntergeladene Audios
    ├── transcripts/         # Transkripte
    ├── summaries/           # Zusammenfassungen
    ├── chapters/            # Kapitel-Daten
    └── podcasts/            # Exportierte MP3s
```

---

## ⚙️ Installation

### Voraussetzungen
- Docker + Docker Compose
- 8+ GB RAM (16 GB empfohlen)
- 20+ GB freier Speicher

### Schnellstart

```bash
# 1. Repository klonen
git clone <repo-url> youtube-ai-suite
cd youtube-ai-suite

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env

# 3. Starten
docker compose up -d

# 4. Ollama-Modell laden (optional aber empfohlen)
docker compose exec ollama ollama pull llama3

# 5. Dashboard öffnen
# http://<server-ip>:3000
```

---

## 🔧 Konfiguration (.env)

```env
# Datenbank
POSTGRES_USER=yt_user
POSTGRES_PASSWORD=sicheres_passwort
POSTGRES_DB=yt_ai_suite

# Sicherheit
SECRET_KEY=zufaelliger_langer_schluessel

# KI / LLM
OLLAMA_URL=http://ollama:11434
OLLAMA_MODELL=llama3
OPENAI_API_KEY=               # Optional

# Whisper
WHISPER_MODELL=base           # tiny|base|small|medium|large
WHISPER_GERAET=cpu            # cpu|cuda
WHISPER_BERECHNUNG=int8       # int8|float16|float32
```

### Whisper-Modelle

| Modell | Größe  | RAM   | Geschwindigkeit | Genauigkeit |
|--------|--------|-------|-----------------|-------------|
| tiny   | 75 MB  | 1 GB  | ⚡⚡⚡⚡          | ⭐⭐         |
| base   | 145 MB | 1 GB  | ⚡⚡⚡           | ⭐⭐⭐       |
| small  | 466 MB | 2 GB  | ⚡⚡             | ⭐⭐⭐⭐     |
| medium | 1.5 GB | 5 GB  | ⚡              | ⭐⭐⭐⭐⭐   |
| large  | 2.9 GB | 10 GB | 🐢              | ⭐⭐⭐⭐⭐   |

### Ollama-Modelle

| Modell       | Größe  | RAM   | Empfehlung              |
|--------------|--------|-------|-------------------------|
| llama3.2:1b  | 1.3 GB | 4 GB  | Minimale Hardware       |
| llama3.2:3b  | 2.0 GB | 6 GB  | Gute Balance            |
| llama3       | 4.7 GB | 8 GB  | Empfohlen (16 GB RAM)   |
| mistral      | 4.1 GB | 8 GB  | Alternative             |

---

## 📡 API-Dokumentation

### Jobs

| Method | Endpoint                      | Beschreibung              |
|--------|-------------------------------|---------------------------|
| POST   | /api/jobs/                    | Job erstellen             |
| GET    | /api/jobs/                    | Alle Jobs auflisten       |
| GET    | /api/jobs/{id}                | Job abrufen               |
| DELETE | /api/jobs/{id}                | Job löschen               |
| POST   | /api/jobs/{id}/abbrechen      | Job abbrechen             |
| GET    | /api/jobs/{id}/video          | Video-Ergebnisse          |
| GET    | /api/jobs/{id}/fortschritt    | Fortschritt abfragen      |
| DELETE | /api/jobs/batch/abgebrochen   | Fehlerhafte Jobs löschen  |

### Export

| Method | Endpoint                | Format     |
|--------|-------------------------|------------|
| GET    | /api/export/{id}/txt    | Plaintext  |
| GET    | /api/export/{id}/markdown | Markdown |
| GET    | /api/export/{id}/json   | JSON       |
| GET    | /api/export/{id}/podcast | MP3       |

### Suche + Chat

| Method | Endpoint              | Beschreibung        |
|--------|-----------------------|---------------------|
| POST   | /api/suche/           | Volltextsuche       |
| POST   | /api/chat/{id}        | KI-Chat             |
| DELETE | /api/chat/{id}/verlauf | Chat-Verlauf löschen|

### Job-Status

```
warteschlange  → Job wartet in der Queue
herunterladen  → Video wird heruntergeladen
verarbeitung   → Audio wird verarbeitet
transkription  → Whisper transkribiert
zusammenfassung→ LLM erstellt Zusammenfassung
abgeschlossen  → Fertig
fehler         → Fehler aufgetreten
abgebrochen    → Vom Nutzer abgebrochen
```

---

## 🔌 WebSocket

```javascript
// Echtzeit-Fortschritt für einen Job
const ws = new WebSocket("ws://server:8000/api/jobs/ws/{job_id}");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
// → {"fortschritt": 45.0, "status": "transkription"}

// Alle Jobs als Live-Stream
const ws = new WebSocket("ws://server:8000/api/jobs/ws");
```

---

## 🔧 Worker skalieren

```bash
# 4 parallele Worker
docker compose up --scale worker=4 -d
```

---

## 🗺️ Geplante Features

- [ ] GPU-Unterstützung (CUDA)
- [ ] Playlist-Batch-Verarbeitung
- [ ] Login-System / Multi-User
- [ ] KI-Chat mit Vektorsuche (pgvector)
- [ ] Automatische Clip-Extraktion
- [ ] Social-Media-Export
- [ ] E-Mail-Benachrichtigungen
- [ ] Obsidian/Notion-Export
- [ ] Anki-Karteikarten-Export

---

## 🐛 Bekannte Probleme & Lösungen

### QNAP NAS
- Nginx hat Berechtigungsprobleme → Python http.server verwenden
- Volume-Mounts können durch QNAP-Security blockiert werden

### PostgreSQL Enum
- SQLAlchemy erstellt Enums mit Großbuchstaben
- Fix: `SAEnum` mit expliziten String-Werten verwenden

### Whisper auf CPU
- Langsam bei großen Modellen → `tiny` oder `base` für Heimserver
- `int8` Compute-Type für maximale CPU-Performance

---

## 📜 Lizenz

MIT License – frei verwendbar für private und kommerzielle Projekte.
```

---

## 2. 🤖 Projekt-Prompt (für andere KIs)

```markdown
# YouTube AI Analysis Suite – Vollständiger Projekt-Prompt

## Projektübersicht

Du sollst an einem vollständig funktionierenden, selbst gehosteten
YouTube-Analyse-System arbeiten. Das Projekt heißt "YouTube AI Analysis Suite"
und läuft als Docker Microservice-Architektur auf einem QNAP NAS (Linux,
ARM/x86, 16 GB RAM).

## Tech-Stack

### Backend
- **API**: FastAPI (Python 3.11) mit async/await
- **Datenbank**: PostgreSQL 16 mit SQLAlchemy (async)
- **Queue**: Redis 7 mit eigenem Queue-Manager (kein RQ/Celery)
- **Worker**: Python-Prozesse die Redis-Queue pollen

### KI/ML
- **Transkription**: Faster-Whisper (CPU, int8, Modelle: tiny/base/small/medium/large)
- **LLM**: Ollama (lokal, llama3) oder OpenAI API als Fallback
- **Audio**: FFmpeg für Extraktion und Normalisierung
- **Download**: yt-dlp für YouTube

### Frontend
- **Server**: Python http.server (kein Nginx wegen QNAP-Berechtigungsproblemen)
- **UI**: Vanilla JavaScript (kein React/Vue)
- **Styling**: CSS Custom Properties, Dark Theme
- **API-URL**: Hardcoded `http://192.168.178.40:8000/api`

## Datenbankschema

### Tabelle: jobs
```sql
id             UUID PRIMARY KEY
url            VARCHAR(2048)
status         ENUM (warteschlange|herunterladen|verarbeitung|
                     transkription|zusammenfassung|abgeschlossen|
                     fehler|abgebrochen)
prioritaet     INTEGER DEFAULT 0
optionen       JSONB
fehlermeldung  TEXT
fortschritt    FLOAT DEFAULT 0.0
erstellt_am    TIMESTAMP
gestartet_am   TIMESTAMP
beendet_am     TIMESTAMP
```

### Tabelle: videos
```sql
id              UUID PRIMARY KEY
job_id          UUID
youtube_id      VARCHAR(20) UNIQUE
titel           VARCHAR(512)
beschreibung    TEXT
kanal           VARCHAR(256)
dauer           INTEGER (Sekunden)
hochladedatum   VARCHAR(20)
thumbnail_url   VARCHAR(2048)
transkript      TEXT
zusammenfassung TEXT
kapitel         JSONB
audio_pfad      VARCHAR(512)
podcast_pfad    VARCHAR(512)
erstellt_am     TIMESTAMP
```

## Wichtige Implementierungsdetails

### PostgreSQL Enum – KRITISCH
SQLAlchemy darf NICHT den Python-Enum-Klassen-Namen verwenden.
Stattdessen MUSS `SAEnum` mit expliziten String-Werten verwendet werden:

```python
from sqlalchemy import Enum as SAEnum

jobstatus_typ = SAEnum(
    "warteschlange", "herunterladen", "verarbeitung",
    "transkription", "zusammenfassung", "abgeschlossen",
    "fehler", "abgebrochen",
    name="jobstatus"
)
```

NIEMALS:
```python
# FALSCH – erzeugt GROSSBUCHSTABEN in PostgreSQL!
Column(Enum(JobStatus), ...)
```

### Status als String
In `schemas.py` muss `status` als `str` definiert sein, nicht als Enum:
```python
class JobAntwort(BaseModel):
    status: str  # NICHT: status: JobStatus
```

### CORS-Konfiguration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # False wenn allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Worker-Pattern
Worker polllen Redis alle 2 Sekunden:
```python
while True:
    for schlange in ["yt_jobs_prioritaet", "yt_jobs_normal"]:
        raw = r.lpop(schlange)
        if raw:
            verarbeiten(job_id, optionen)
            break
    else:
        time.sleep(2)
```

### Abbruch-Mechanismus
- Frontend: POST /api/jobs/{id}/abbrechen
- API: Setzt Redis-Flag `abbruch:{job_id}` + löscht Job aus DB
- Worker: Prüft Flag alle 10 Transkriptions-Segmente

### Fortschritt-Tracking
Redis Key `fortschritt:{job_id}` mit TTL 3600s:
```json
{"fortschritt": 45.0, "status": "transkription"}
```

Fortschritts-Schritte:
- 5%  → herunterladen
- 20% → verarbeitung
- 35% → transkription start
- 70% → transkription ende
- 80% → zusammenfassung
- 100% → abgeschlossen

## API-Endpunkte

```
POST   /api/jobs/                    Job erstellen
GET    /api/jobs/?limit=50           Jobs auflisten
GET    /api/jobs/{id}                Job abrufen
DELETE /api/jobs/{id}                Job löschen
POST   /api/jobs/{id}/abbrechen      Job abbrechen + löschen
GET    /api/jobs/{id}/video          Video-Ergebnisse
GET    /api/jobs/{id}/fortschritt    Fortschritt (Redis)
DELETE /api/jobs/batch/abgebrochen   Fehlerhafte Jobs löschen
GET    /api/jobs/warteschlange/statistik Queue-Länge

POST   /api/suche/                   Volltextsuche
GET    /api/export/{id}/txt          TXT Export
GET    /api/export/{id}/markdown     Markdown Export
GET    /api/export/{id}/json         JSON Export
GET    /api/export/{id}/podcast      MP3 Download
POST   /api/chat/{id}                KI-Chat
DELETE /api/chat/{id}/verlauf        Chat löschen

WS     /api/jobs/ws/{job_id}         Job-Fortschritt Stream
WS     /api/jobs/ws                  Alle Jobs Stream
GET    /api/gesundheit               Health Check
```

## Frontend-Struktur

Das Frontend ist eine Single-Page-Application in Vanilla JS:

- `tab(name)` – Dashboard/Suche umschalten
- `starten()` – Neuen Job erstellen
- `laden()` – Jobs von API laden (alle 5s)
- `rendern()` – Job-Liste rendern
- `stats()` – Statistik-Leiste aktualisieren
- `detail(id)` – Job-Detail Modal öffnen
- `jobAbbrechen(id, btn)` – Job abbrechen
- `jobLoeschen(id, btn)` – Job löschen
- `alleAbgebrochenLoeschen()` – Batch-Löschen
- `suchen()` – Volltextsuche
- `chatSenden()` – KI-Chat Nachricht senden
- `exp(id, format)` – Export öffnen

## Bekannte Probleme + Lösungen

1. **QNAP Nginx 403**: Python http.server statt Nginx verwenden
2. **Enum Großbuchstaben**: SAEnum mit String-Werten verwenden
3. **CORS bei 500-Fehlern**: Exception-Handler mit CORS-Headern
4. **Cache-Probleme**: Cache-Control: no-store Header im Frontend-Server
5. **dpkg Fehler**: `python:3.11-slim-bookworm` statt `python:3.11-slim`

## Verzeichnisstruktur im Container

```
/app/data/
├── audio/{job_id}/          WAV-Dateien
├── transcripts/             (nicht aktiv genutzt)
├── summaries/               (nicht aktiv genutzt)
├── chapters/                (nicht aktiv genutzt)
└── podcasts/                MP3-Dateien
```

## Umgebungsvariablen

```env
DATABASE_URL=postgresql://yt_user:pass@postgres:5432/yt_ai_suite
REDIS_URL=redis://redis:6379
OLLAMA_URL=http://ollama:11434
OLLAMA_MODELL=llama3
OPENAI_API_KEY=
WHISPER_MODELL=base
WHISPER_GERAET=cpu
WHISPER_BERECHNUNG=int8
SECRET_KEY=geheimer_schluessel
```
```

---

## 3. 🚀 Super-Prompt

```markdown
# Super-Prompt: YouTube AI Analysis Suite

Du bist ein erfahrener Senior Software-Architekt, der an der
"YouTube AI Analysis Suite" arbeitet – einer produktionsreifen,
selbst gehosteten KI-Plattform.

## Deine Aufgabe

Analysiere den folgenden Code/Fehler/Anfrage und liefere eine
vollständige, sofort einsetzbare Lösung. Antworte IMMER mit:

1. **Ursachen-Analyse** (1-3 Sätze, präzise)
2. **Vollständiger Code** (komplett, nicht abgeschnitten)
3. **Deploy-Befehl** (sofort ausführbar)
4. **Verifikations-Test** (curl oder Browser-Test)

## System-Kontext

### Hardware
- QNAP NAS, Linux 5.10.60-qnap
- 16 GB RAM, kein GPU
- Docker + Docker Compose

### Kritische Regeln

**REGEL 1 – PostgreSQL Enum**
IMMER `SAEnum` mit expliziten String-Werten in Kleinbuchstaben:
```python
from sqlalchemy import Enum as SAEnum
Column(SAEnum("warteschlange","herunterladen",...,name="jobstatus"))
```
NIEMALS `Column(Enum(PythonEnumKlasse))` – das erzeugt Großbuchstaben!

**REGEL 2 – Pydantic Status**
```python
class JobAntwort(BaseModel):
    status: str  # String, NICHT Enum-Typ
```

**REGEL 3 – Frontend**
- Python http.server statt Nginx (QNAP Berechtigungsproblem)
- API-URL: `const API = "http://192.168.178.40:8000/api";`
- Kein React/Vue – nur Vanilla JS

**REGEL 4 – CORS**
```python
CORSMiddleware(allow_origins=["*"], allow_credentials=False)
```

**REGEL 5 – Worker Status-Updates**
Immer über raw SQL, nie über ORM bei Status-Updates:
```python
await db.execute(text("UPDATE jobs SET status='abgeschlossen' WHERE id=:id"), {"id": job_id})
```

**REGEL 6 – Docker**
Basis-Image: `python:3.11-slim-bookworm` (nicht plain slim)

## Aktueller Stack

```yaml
api:      FastAPI + SQLAlchemy async + asyncpg
worker:   Python + Faster-Whisper + yt-dlp + FFmpeg
frontend: Python http.server + Vanilla JS
db:       PostgreSQL 16 (Enum: Kleinbuchstaben!)
queue:    Redis 7 (eigener Queue-Manager)
llm:      Ollama (llama3) + OpenAI Fallback
```

## Job-Pipeline

```
URL eingeben
    ↓
Redis Queue (yt_jobs_normal/yt_jobs_prioritaet)
    ↓
Worker pollt alle 2s
    ↓
1. yt-dlp Download         → 5%
2. FFmpeg Audio-Processing → 20%
3. Faster-Whisper          → 35-70%
4. Kapitel-Erkennung       → 72%
5. Ollama Zusammenfassung  → 80%
6. Podcast-Export (opt.)   → 95%
7. DB speichern            → 100%
```

## Wenn du Code schreibst

- Vollständig – keine `# ... rest of code` Platzhalter
- Kommentare auf Deutsch
- Fehlerbehandlung immer mit try/except
- Logging mit `log = logging.getLogger("modulname")`
- Alle Imports am Anfang der Datei

## Wenn du Fehler debuggst

1. Zeige die **genaue Fehlerursache** (eine Zeile)
2. Erkläre **warum** es passiert
3. Gib den **minimalen Fix** an
4. Dann den **vollständigen korrigierten Code**

## Deployment-Muster

```bash
# Standard-Deploy
docker compose build --no-cache <service>
docker compose up -d <service>

# DB-Migration
docker compose exec postgres psql -U yt_user -d yt_ai_suite -c "SQL"

# Logs prüfen
docker compose logs <service> --tail=20

# Test
curl -s http://192.168.178.40:8000/api/gesundheit
```
```

---

> 💡 **Tipp:** Den **Super-Prompt** am Anfang jedes Gesprächs mit einer anderen KI einfügen – dann kennt sie sofort alle Regeln und liefert direkt funktionierenden Code ohne die bekannten Fallstricke (Enum-Großbuchstaben, Nginx-Probleme, etc.)!
