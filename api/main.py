#!/usr/bin/env python3
"""
YouTube AI Analysis Suite - API
Haupt-API mit Wartefunktion für Datenbank
"""

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Warte auf Datenbank - korrekter Import
from wait_for_db import wait_for_database

# Routen importieren
from routers import jobs, search, export, chat
from database import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(title="YouTube AI Analysis Suite API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router einbinden
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/api/suche", tags=["search"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

@app.on_event("startup")
async def startup_event():
    """Wird beim Start ausgeführt"""
    log.info("⏳ Warte auf Datenbank...")
    await wait_for_database()
    log.info("✅ Datenbank verbunden, initialisiere...")
    await init_db()
    log.info("🚀 API gestartet")

@app.get("/api/gesundheit")
async def gesundheit():
    return {"status": "ok", "dienst": "YouTube AI Analysis Suite"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)