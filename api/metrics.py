from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
import time
from typing import Callable
from fastapi import Request
import psutil

router = APIRouter(prefix="/metrics", tags=["monitoring"])

# Prometheus Metrics Definitionen
jobs_total = Counter(
    'youtube_ai_jobs_total', 
    'Gesamtanzahl der Jobs',
    ['status']
)

jobs_duration = Histogram(
    'youtube_ai_job_duration_seconds',
    'Dauer der Job-Verarbeitung in Sekunden',
    buckets=[60, 300, 600, 1800, 3600, 7200]
)

active_jobs = Gauge(
    'youtube_ai_active_jobs',
    'Anzahl aktuell aktiver Jobs'
)

queue_size = Gauge(
    'youtube_ai_queue_size',
    'Anzahl wartender Jobs in der Queue',
    ['priority']
)

api_requests = Counter(
    'youtube_ai_api_requests_total',
    'Anzahl API Requests',
    ['method', 'endpoint', 'status']
)

api_duration = Histogram(
    'youtube_ai_api_duration_seconds',
    'Dauer der API Requests',
    ['method', 'endpoint']
)

worker_health = Gauge(
    'youtube_ai_worker_health',
    'Health-Status der Worker (1=healthy, 0=unhealthy)',
    ['worker_id']
)

system_memory = Gauge(
    'youtube_ai_system_memory_bytes',
    'System-Speichernutzung',
    ['type']
)

system_cpu = Gauge(
    'youtube_ai_system_cpu_percent',
    'System-CPU Auslastung'
)

# Middleware für Request-Tracking
async def metrics_middleware(request: Request, call_next: Callable):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    api_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    api_requests.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    return response

@router.get("/")
async def get_metrics():
    """
    Prometheus Metrics Endpoint
    """
    # System-Metrics aktualisieren
    memory = psutil.virtual_memory()
    system_memory.labels(type='total').set(memory.total)
    system_memory.labels(type='available').set(memory.available)
    system_memory.labels(type='used').set(memory.used)
    system_memory.labels(type='free').set(memory.free)
    
    system_cpu.set(psutil.cpu_percent(interval=1))
    
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain"
    )

@router.get("/health")
async def health_check():
    """
    Detaillierter Health-Check für API
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "api": "healthy",
            "database": await check_database(),
            "redis": await check_redis(),
            "workers": await check_workers()
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
    }
    
    # Gesamtstatus berechnen
    for service, status in health_status["services"].items():
        if status != "healthy":
            health_status["status"] = "degraded"
            break
    
    return health_status

async def check_database() -> str:
    """
    Prüft Datenbank-Verbindung
    """
    try:
        from database import get_db
        async for db in get_db():
            await db.execute("SELECT 1")
            return "healthy"
    except:
        return "unhealthy"

async def check_redis() -> str:
    """
    Prüft Redis-Verbindung
    """
    try:
        import redis.asyncio as redis
        from config import REDIS_URL
        r = await redis.from_url(REDIS_URL)
        await r.ping()
        await r.close()
        return "healthy"
    except:
        return "unhealthy"

async def check_workers() -> dict:
    """
    Prüft Worker-Health via Redis Heartbeats
    """
    try:
        import redis.asyncio as redis
        from config import REDIS_URL
        r = await redis.from_url(REDIS_URL)
        
        # Alle Worker-Heartbeats abrufen
        worker_keys = await r.keys("worker:*:heartbeat")
        workers = {}
        
        for key in worker_keys:
            worker_id = key.decode().split(':')[1]
            last_heartbeat = await r.get(key)
            
            if last_heartbeat:
                import datetime
                last_time = datetime.datetime.fromisoformat(last_heartbeat.decode())
                age = (datetime.datetime.now() - last_time).seconds
                
                workers[worker_id] = {
                    "status": "healthy" if age < 60 else "stale",
                    "last_heartbeat": last_heartbeat.decode(),
                    "age_seconds": age
                }
                
                # Worker Health Gauge aktualisieren
                worker_health.labels(worker_id=worker_id).set(1 if age < 60 else 0)
        
        await r.close()
        return workers
    except Exception as e:
        return {"error": str(e)}

# Funktion zum Aktualisieren von Queue-Metrics
async def update_queue_metrics():
    """
    Aktualisiert Queue-Größen für Prometheus
    """
    import redis.asyncio as redis
    from config import REDIS_URL
    
    r = await redis.from_url(REDIS_URL)
    
    for priority in ["normal", "hoch"]:
        queue_key = f"yt_jobs_{priority}"
        size = await r.llen(queue_key)
        queue_size.labels(priority=priority).set(size)
    
    await r.close()