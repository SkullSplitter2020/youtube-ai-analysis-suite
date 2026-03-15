FROM python:3.11-slim-bookworm

WORKDIR /app

# System-Abhängigkeiten
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App kopieren
COPY . .

# Warte-Skript ausführbar machen
RUN chmod +x wait_for_db.py

# Startbefehl mit Wartezeit
CMD python wait_for_db.py && uvicorn main:app --host 0.0.0.0 --port 8000 --reload