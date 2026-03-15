#!/usr/bin/env python3
"""
Wartefunktion für Datenbank
"""
import asyncio
import asyncpg
import os
import sys
import time

async def wait_for_database(max_retries=30, delay=2):
    """Wartet bis Datenbank bereit ist"""
    database_url = os.getenv("DATABASE_URL", "postgresql://yt_user:sicheres_passwort@postgres:5432/yt_ai_suite")
    
    print(f"⏳ Warte auf Datenbank: {database_url}")
    
    for i in range(max_retries):
        try:
            conn = await asyncpg.connect(database_url)
            await conn.execute("SELECT 1")
            await conn.close()
            print(f"✅ Datenbank verbunden nach {i*delay} Sekunden")
            return True
        except Exception as e:
            print(f"⏳ Versuch {i+1}/{max_retries}: {str(e)[:50]}...")
            await asyncio.sleep(delay)
    
    print("❌ Datenbank nicht erreichbar")
    return False

if __name__ == "__main__":
    success = asyncio.run(wait_for_database())
    if not success:
        sys.exit(1)