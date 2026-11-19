from fastapi import APIRouter

from app.api.v1 import auth, candidates, health, jobs, runs

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(jobs.router)
router.include_router(candidates.router)
router.include_router(runs.router)
