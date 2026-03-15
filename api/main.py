from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from database import init_db
from routers import jobs, search, export
import traceback


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="YouTube AI Analysis Suite",
    version="1.0.0",
    lifespan=lebenszyklus
)

# CORS zuerst registrieren – vor allem anderen!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# CORS auch bei 500-Fehlern sicherstellen
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


app.include_router(jobs.router,   prefix="/api/jobs",   tags=["Jobs"])
app.include_router(search.router, prefix="/api/suche",  tags=["Suche"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])


@app.get("/api/gesundheit")
async def gesundheitscheck():
    return {"status": "ok", "dienst": "YouTube AI Analysis Suite"}