from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers import auth, spaces, tasks, invitations, users, schedule, daily_plan, events
from app.core.scheduler import scheduler, setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="OurWay API", version="0.1.0", lifespan=lifespan)

origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(spaces.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(invitations.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(schedule.router, prefix="/api/v1")
app.include_router(daily_plan.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "ok", "service": "OurWay API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
