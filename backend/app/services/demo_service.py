"""The demo account: realistic jobs and candidates from the synthetic stress-test corpus.

eval/stress/samples holds generated JDs and resume PDFs (no real people). The demo gets a
candidate database across several professions, three jobs (one PDF, two pasted), and a
short-list on each job. Scoring then happens in the API's background worker like any
other upload, so the demo shows the real pipeline, not canned numbers.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.models import User
from app.services import auth_service, candidate_service, job_service
from app.services.candidate_service import ResumeFile
from app.services.scoring_service import PdfInput
from app.storage.base import Storage

log = get_logger(__name__)

CORPUS = Path(__file__).resolve().parents[3] / "eval" / "stress" / "samples"

# Resume profiles in the candidate database (4 resumes each: strong, mid, junior, switcher).
DATABASE_PROFILES = (
    "backend_python",
    "frontend_react",
    "data_engineer",
    "ml_engineer",
    "devops_sre",
    "product_manager",
    "engineering_manager",
    "ux_designer",
    "hr_recruiter",
    "digital_marketing",
)


@dataclass(frozen=True)
class DemoJob:
    jd: str  # corpus JD id
    shortlist: tuple[str, ...]  # resume ids added (and scored) on the job


DEMO_JOBS = (
    DemoJob("jd_002", ("cv_001", "cv_002", "cv_004", "cv_009")),  # backend, PDF
    DemoJob("jd_007", ("cv_005", "cv_006", "cv_007")),  # frontend, pasted
    DemoJob("jd_071", ("cv_069", "cv_070", "cv_065")),  # product manager, pasted
)


@dataclass(frozen=True)
class DemoSummary:
    user: User
    candidates: int
    jobs: int
    queued: int


def _manifest(corpus: Path) -> dict[str, dict[str, dict[str, object]]]:
    data = json.loads((corpus / "manifest.json").read_text())
    return {
        "jds": {j["id"]: j for j in data["jds"]},
        "resumes": {r["id"]: r for r in data["resumes"]},
    }


async def seed(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    *,
    reset: bool = False,
    corpus: Path = CORPUS,
) -> DemoSummary:
    if not (corpus / "manifest.json").exists():
        raise NotFoundError(f"Demo corpus not found at {corpus}")
    manifest = _manifest(corpus)
    email = settings.demo_email
    if reset:
        existing = await auth_service.get_user_by_email(session, email)
        if existing is not None:
            await session.execute(delete(User).where(User.id == existing.id))
            await session.commit()
            log.info("demo_reset", user_id=str(existing.id))
    user = await auth_service.upsert_user(
        session,
        email=email,
        name="Demo Recruiter",
        password=settings.demo_password.get_secret_value(),
        is_demo=True,
    )

    paths = {
        r_id: corpus / str(r["path"])
        for r_id, r in manifest["resumes"].items()
        if r["profile"] in DATABASE_PROFILES and str(r["format"]).endswith("pdf")
    }
    files = [ResumeFile(path.name, path.read_bytes()) for path in paths.values()]
    added, errors = await candidate_service.add_resumes(session, storage, settings, user, files)
    if errors:
        log.warning("demo_resume_errors", errors=[e.model_dump() for e in errors])
    by_filename = {document.original_filename: candidate for candidate, document in added}
    by_resume = {r_id: by_filename[p.name] for r_id, p in paths.items() if p.name in by_filename}

    queued = 0
    for demo in DEMO_JOBS:
        meta = manifest["jds"][demo.jd]
        path = corpus / str(meta["path"])
        jd: PdfInput | str = (
            PdfInput(path.name, path.read_bytes()) if path.suffix == ".pdf" else path.read_text()
        )
        job = await job_service.create_job(session, storage, settings, user, jd)
        ids = [by_resume[r].id for r in demo.shortlist if r in by_resume]
        queued += len(await job_service.add_candidates(session, user, job.id, ids, source="upload"))
    log.info("demo_seeded", user_id=str(user.id), candidates=len(added), jobs=len(DEMO_JOBS))
    return DemoSummary(user=user, candidates=len(added), jobs=len(DEMO_JOBS), queued=queued)
