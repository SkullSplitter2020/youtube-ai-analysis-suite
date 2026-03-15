import asyncio
import logging
import psutil
import json
from datetime import datetime
from typing import Dict, Any
import aiohttp
import redis.asyncio as redis
import asyncpg

log = logging.getLogger("health")

class WorkerHealthCheck:
    def __init__(self, worker_id: str, redis_url: str, postgres_url: str):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        self.last_heartbeat = datetime.now()
        self.current_job = None
        self.health_status = "healthy"
        self.error_count = 0
        
    async def start_health_server(self, port: int = 8081):
        """
        Startet Health-Check HTTP-Server
        """
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/metrics", self.metrics)
        app.router.add_get("/ready", self.readiness)
        app.router.add_get("/live", self.liveness)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        log.info(f"Health-Check Server läuft auf Port {port}")
        
    async def health_check(self, request):
        """
        Detaillierter Health-Check mit System-Informationen
        """
        try:
            # Redis check
            redis_ok = await self._check_redis()
            
            # PostgreSQL check
            postgres_ok = await self._check_postgres()
            
            # System resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Worker status
            time_since_heartbeat = (datetime.now() - self.last_heartbeat).seconds
            
            status = {
                "worker_id": self.worker_id,
                "status": self.health_status,
                "timestamp": datetime.now().isoformat(),
                "checks": {
                    "redis": "healthy" if redis_ok else "unhealthy",
                    "postgres": "healthy" if postgres_ok else "unhealthy",
                },
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available // 1024 // 1024,
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free // 1024 // 1024 // 1024
                },
                "worker": {
                    "current_job": self.current_job,
                    "last_heartbeat_seconds": time_since_heartbeat,
                    "error_count": self.error_count,
                    "uptime": self._get_uptime()
                }
            }
            
            # Gesamtstatus
            if not redis_ok or not postgres_ok or time_since_heartbeat > 60:
                status["status"] = "degraded"
            if self.error_count > 10:
                status["status"] = "unhealthy"
                
            return web.json_response(status)
            
        except Exception as e:
            log.error(f"Health-Check fehlgeschlagen: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500
            )
    
    async def metrics(self, request):
        """
        Prometheus-Metrics im Text-Format
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = []
            
            # CPU Metrics
            metrics.append("# HELP worker_cpu_percent CPU Auslastung in Prozent")
            metrics.append("# TYPE worker_cpu_percent gauge")
            metrics.append(f"worker_cpu_percent {cpu_percent}")
            
            # Memory Metrics
            metrics.append("# HELP worker_memory_percent Speicherauslastung in Prozent")
            metrics.append("# TYPE worker_memory_percent gauge")
            metrics.append(f"worker_memory_percent {memory.percent}")
            metrics.append(f"worker_memory_available_bytes {memory.available}")
            
            # Disk Metrics
            metrics.append("# HELP worker_disk_percent Festplattenauslastung in Prozent")
            metrics.append("# TYPE worker_disk_percent gauge")
            metrics.append(f"worker_disk_percent {disk.percent}")
            metrics.append(f"worker_disk_free_bytes {disk.free}")
            
            # Worker Metrics
            metrics.append("# HELP worker_errors_total Anzahl der Fehler")
            metrics.append("# TYPE worker_errors_total counter")
            metrics.append(f"worker_errors_total {self.error_count}")
            
            metrics.append("# HELP worker_healthy Worker Status (1=healthy, 0=unhealthy)")
            metrics.append("# TYPE worker_healthy gauge")
            metrics.append(f"worker_healthy {1 if self.health_status == 'healthy' else 0}")
            
            metrics.append("# HELP worker_current_job Aktuell verarbeiteter Job")
            metrics.append("# TYPE worker_current_job gauge")
            metrics.append(f"worker_current_job {1 if self.current_job else 0}")
            
            return web.Response(
                text="\n".join(metrics),
                content_type="text/plain"
            )
            
        except Exception as e:
            log.error(f"Metrics fehlgeschlagen: {e}")
            return web.Response(status=500)
    
    async def readiness(self, request):
        """
        Readiness Probe für Kubernetes/Docker
        """
        redis_ok = await self._check_redis()
        postgres_ok = await self._check_postgres()
        
        if redis_ok and postgres_ok:
            return web.json_response({"status": "ready"})
        else:
            return web.json_response({"status": "not ready"}, status=503)
    
    async def liveness(self, request):
        """
        Liveness Probe für Kubernetes/Docker
        """
        if self.health_status != "unhealthy":
            return web.json_response({"status": "alive"})
        else:
            return web.json_response({"status": "dead"}, status=503)
    
    async def _check_redis(self) -> bool:
        """
        Prüft Redis-Verbindung
        """
        try:
            r = await redis.from_url(self.redis_url)
            await r.ping()
            await r.close()
            return True
        except Exception as e:
            log.error(f"Redis Health-Check fehlgeschlagen: {e}")
            return False
    
    async def _check_postgres(self) -> bool:
        """
        Prüft PostgreSQL-Verbindung
        """
        try:
            conn = await asyncpg.connect(self.postgres_url)
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception as e:
            log.error(f"PostgreSQL Health-Check fehlgeschlagen: {e}")
            return False
    
    def _get_uptime(self) -> str:
        """
        Berechnet Uptime
        """
        import time
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

# Heartbeat-Funktion für Worker
async def heartbeat_worker(worker_id: str, redis_url: str, interval: int = 30):
    """
    Sendet regelmäßig Heartbeats an Redis
    """
    r = await redis.from_url(redis_url)
    while True:
        try:
            await r.setex(
                f"worker:{worker_id}:heartbeat",
                interval * 2,
                datetime.now().isoformat()
            )
            await asyncio.sleep(interval)
        except Exception as e:
            log.error(f"Heartbeat fehlgeschlagen: {e}")
            await asyncio.sleep(5)