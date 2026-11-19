"""Search a user's candidate database by keywords or any pasted text.

Postgres full-text search (docs/plan-jobs-and-search.md):
1. The query is split into terms with the same `english` parser that indexed the resumes
   (stemmed: "managed" -> "manag"); numbers and stop words are dropped.
2. A resume is a hit if it contains ANY term (an OR query), so a pasted JD with 80 terms
   still finds resumes; an AND query would find none.
3. Hits are ranked by the share of query terms they contain, each term weighted by how
   rare it is in this user's database (IDF): "kubernetes" counts more than "team".
   `ts_rank_cd` (term density) breaks ties.
"""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, func, literal, select, text
from sqlalchemy.dialects.postgresql import ARRAY, TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.db.models import Candidate, Document, Job, JobCandidate, ScoringRun, User
from app.schemas.workspace import CandidateJobRef, SearchHit, SearchResult, SearchTerm
from app.services.candidate_service import brief
from app.services.run_view import whole_score

MAX_QUERY_CHARS = 20_000
MAX_TERMS = 200
# ts_headline markers; never present in extracted resume text, rendered as <mark> in the UI.
MARK_START, MARK_END = "\u0001", "\u0002"
_HEADLINE_OPTIONS = (
    f"StartSel={MARK_START}, StopSel={MARK_END}, MaxFragments=2, MaxWords=22, MinWords=10, "
    "FragmentDelimiter=' … '"
)


@dataclass(frozen=True)
class QueryTerms:
    lexemes: list[str]  # unique, in query order
    display: dict[str, str]  # lexeme -> the word as typed


async def parse_query(session: AsyncSession, query: str) -> QueryTerms:
    # Hyphenated words come back whole ("end-to-end") and as parts; keep only the parts,
    # which match both "end-to-end" and "end to end" and aren't counted twice.
    rows = (
        await session.execute(
            text(
                "SELECT token, lexemes FROM ts_debug('english', :q) "
                "WHERE lexemes <> '{}' AND alias NOT IN ('asciihword', 'hword', 'numhword')"
            ),
            {"q": query},
        )
    ).all()
    display: dict[str, str] = {}
    for token, lexemes in rows:
        for lexeme in lexemes:
            if lexeme.replace(".", "").isdigit():
                continue  # "5", "2021": matches almost every resume
            display.setdefault(lexeme, token)
    lexemes = list(display)[:MAX_TERMS]
    return QueryTerms(lexemes=lexemes, display={k: display[k] for k in lexemes})


def _or_query(lexemes: list[str]) -> Any:
    """An OR tsquery of already-normalised lexemes (cast, not to_tsquery: no re-stemming)."""
    quoted = " | ".join("'" + lexeme.replace("'", "''") + "'" for lexeme in lexemes)
    return cast(literal(quoted, Text), TSQUERY)


async def search(
    session: AsyncSession, owner: User, query: str, *, limit: int = 25
) -> SearchResult:
    query = query.strip()
    if not query:
        raise ValidationFailedError("Type some keywords or paste text to search for")
    if len(query) > MAX_QUERY_CHARS:
        raise ValidationFailedError(f"Search text is too long (max {MAX_QUERY_CHARS} characters)")

    total = (
        await session.execute(
            select(func.count()).select_from(Candidate).where(Candidate.owner_id == owner.id)
        )
    ).scalar_one()
    terms = await parse_query(session, query)
    if not terms.lexemes or total == 0:
        return SearchResult(query=query, total_candidates=total, terms=[], hits=[])

    tsquery = _or_query(terms.lexemes)
    terms_array = cast(literal(terms.lexemes, ARRAY(Text)), ARRAY(Text))
    # Query terms present in THIS resume. Compound selects aren't auto-correlated, so the
    # resume side must be correlated explicitly (else it reads every resume's terms).
    matched = func.array(
        select(func.unnest(terms_array))
        .intersect(
            select(func.unnest(func.tsvector_to_array(Candidate.search_vector))).correlate(
                Candidate
            )
        )
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(
                Candidate.id,
                matched.label("matched"),
                func.ts_rank_cd(Candidate.search_vector, tsquery, 32).label("density"),
            ).where(Candidate.owner_id == owner.id, Candidate.search_vector.op("@@")(tsquery))
        )
    ).all()

    # Document frequency of each term among this owner's resumes -> IDF weight.
    df: dict[str, int] = {}
    for row in rows:
        for lexeme in row.matched:
            df[lexeme] = df.get(lexeme, 0) + 1
    idf = {t: math.log(1 + total / max(df.get(t, 0), 1)) for t in terms.lexemes}
    # Terms no resume contains can't separate candidates; leaving them out of the
    # denominator keeps "match" meaningful when a pasted JD has many such words.
    present = [t for t in terms.lexemes if df.get(t)]
    denominator = sum(idf[t] for t in present) or 1.0

    scored = sorted(
        ((sum(idf[t] for t in row.matched) / denominator, float(row.density), row) for row in rows),
        key=lambda item: (-item[0], -item[1]),
    )[:limit]
    if not scored:
        return SearchResult(
            query=query, total_candidates=total, terms=list(terms.display.values()), hits=[]
        )

    ids = [row.id for _, _, row in scored]
    details = {
        r[0].id: r
        for r in (
            await session.execute(
                select(
                    Candidate,
                    Document,
                    func.ts_headline(
                        "english", Candidate.search_text, tsquery, _HEADLINE_OPTIONS
                    ).label("snippet"),
                )
                .join(Document, Document.id == Candidate.resume_document_id)
                .where(Candidate.id.in_(ids))
            )
        ).all()
    }
    jobs = await _jobs_for(session, ids)

    hits = []
    for share, _, row in scored:
        candidate, document, snippet = details[row.id]
        found = set(row.matched)
        hits.append(
            SearchHit(
                candidate=brief(candidate, document),
                match=round(share * 100),
                terms=[
                    SearchTerm(term=terms.display[t], matched=t in found)
                    for t in terms.lexemes
                    if df.get(t)
                ],
                snippet=" ".join(snippet.split()),
                jobs=jobs.get(row.id, []),
            )
        )
    return SearchResult(
        query=query,
        total_candidates=total,
        terms=list(terms.display.values()),
        hits=hits,
    )


async def _jobs_for(
    session: AsyncSession, candidate_ids: list[UUID]
) -> dict[UUID, list[CandidateJobRef]]:
    stmt = (
        select(JobCandidate, Job.title, ScoringRun.score)
        .join(Job, Job.id == JobCandidate.job_id)
        .outerjoin(ScoringRun, ScoringRun.id == JobCandidate.run_id)
        .where(JobCandidate.candidate_id.in_(candidate_ids))
        .order_by(JobCandidate.created_at)
    )
    out: dict[UUID, list[CandidateJobRef]] = {}
    for jc, title, score in (await session.execute(stmt)).all():
        out.setdefault(jc.candidate_id, []).append(
            CandidateJobRef(
                job_id=jc.job_id,
                job_title=title,
                job_candidate_id=jc.id,
                status=jc.status,
                score=whole_score(score) if jc.status == "scored" else None,
            )
        )
    return out
