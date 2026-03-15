-- Benutzer erstellen
CREATE USER yt_user WITH PASSWORD 'sicheres_passwort';

-- Datenbank erstellen
CREATE DATABASE yt_ai_suite OWNER yt_user;

-- Mit der Datenbank verbinden
\c yt_ai_suite

-- Enum-Typ für Job-Status
CREATE TYPE jobstatus AS ENUM (
    'warteschlange', 'herunterladen', 'verarbeitung',
    'transkription', 'zusammenfassung', 'abgeschlossen',
    'fehler', 'abgebrochen'
);

-- Jobs Tabelle
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(2048) NOT NULL,
    status jobstatus NOT NULL DEFAULT 'warteschlange',
    prioritaet INTEGER DEFAULT 0,
    optionen JSONB,
    fehlermeldung TEXT,
    fortschritt FLOAT DEFAULT 0.0,
    erstellt_am TIMESTAMP DEFAULT NOW(),
    gestartet_am TIMESTAMP,
    beendet_am TIMESTAMP
);

-- Videos Tabelle
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    youtube_id VARCHAR(20) UNIQUE,
    titel VARCHAR(512),
    beschreibung TEXT,
    kanal VARCHAR(256),
    dauer INTEGER,
    hochladedatum VARCHAR(20),
    thumbnail_url VARCHAR(2048),
    transkript TEXT,
    zusammenfassung TEXT,
    kapitel JSONB,
    audio_pfad VARCHAR(512),
    podcast_pfad VARCHAR(512),
    erstellt_am TIMESTAMP DEFAULT NOW()
);

-- Indizes
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_erstellt_am ON jobs(erstellt_am);
CREATE INDEX idx_videos_youtube_id ON videos(youtube_id);
CREATE INDEX idx_videos_job_id ON videos(job_id);
EOF
