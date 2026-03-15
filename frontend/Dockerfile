FROM python:3.11-slim-bookworm

WORKDIR /app

# Kopiere die Dateien
COPY server.py .
COPY index.html .
COPY style.css .
COPY app.js .

# Prüfe ob Dateien vorhanden sind
RUN ls -la

# Port freigeben
EXPOSE 3000

# Startbefehl
CMD ["python", "-u", "server.py"]