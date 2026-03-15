FROM python:3.11-alpine

WORKDIR /app

COPY index.html .
COPY style.css  .
COPY app.js     .

RUN adduser -D webuser && \
    chown -R webuser:webuser /app && \
    chmod -R 755 /app

# Kleiner Python-Server mit Cache-Deaktivierung
COPY server.py .

USER webuser
EXPOSE 80
CMD ["python3", "server.py"]