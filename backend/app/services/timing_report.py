"""How long each stage takes, read back from what the pipeline stores (`make timings`).

Every number comes from stored rows, so the report answers "where does the time go?"
for any period without re-running anything:

- extraction: documents.extraction_ms
- JD parsing: rubrics.parse_ms and the jobs' queued/started/finished timestamps
- model calls: llm_calls.latency_ms (manual mode: time until the answer file appeared)
- resume scoring: scoring_runs.timings per step, job_candidates queue wait / scoring time
- search: search_events
"""

# The f-strings below only splice fixed column names and step keys from this module; the
# one outside value (days) is always a bound parameter.
# ruff: noqa: S608

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_STATS = """
    count({v}) AS n,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY {v}) AS p50,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY {v}) AS p95,
    max({v}) AS max
"""
_MS = "EXTRACT(EPOCH FROM ({end} - {start})) * 1000"


@dataclass
class Section:
    title: str
    note: str
    columns: list[str]
    rows: list[tuple[Any, ...]]


async def _rows(session: AsyncSession, sql: str, days: int) -> list[tuple[Any, ...]]:
    result = await session.execute(text(sql), {"days": days})
    return [tuple(r) for r in result.all()]


def _since(column: str = "created_at") -> str:
    return f"{column} >= now() - make_interval(days => :days)"


async def build(session: AsyncSession, days: int) -> list[Section]:
    s: list[Section] = []
    stat = _STATS.format

    s.append(
        Section(
            "Text extraction",
            "documents.extraction_ms; one row per new file (re-uploads reuse the stored text)",
            ["kind", "extractor", "n", "p50 ms", "p95 ms", "max ms", "ms/page p50"],
            await _rows(
                session,
                f"""SELECT kind, extractor, {stat(v="extraction_ms")},
                    percentile_cont(0.5) WITHIN GROUP
                        (ORDER BY extraction_ms::float / greatest(page_count, 1))
                FROM documents WHERE extraction_ms IS NOT NULL AND {_since()}
                GROUP BY kind, extractor ORDER BY kind, extractor""",
                days,
            ),
        )
    )
    s.append(
        Section(
            "Slowest extractions",
            "candidates for OCR / size limits",
            ["kind", "file", "pages", "chars", "ms"],
            await _rows(
                session,
                f"""SELECT kind, left(original_filename, 40), page_count, char_count,
                    extraction_ms
                FROM documents WHERE extraction_ms IS NOT NULL AND {_since()}
                ORDER BY extraction_ms DESC LIMIT 5""",
                days,
            ),
        )
    )
    s.append(
        Section(
            "JD parsing",
            "rubrics.parse_ms (model + repair + validation); jobs: queue wait and parse time",
            ["measure", "n", "p50 ms", "p95 ms", "max ms"],
            await _rows(
                session,
                f"""SELECT 'rubric parse', {stat(v="parse_ms")} FROM rubrics
                    WHERE parse_ms IS NOT NULL AND {_since()}
                UNION ALL
                SELECT 'job queue wait',
                    {stat(v=_MS.format(end="parse_started_at", start="parse_queued_at"))}
                    FROM jobs WHERE parse_started_at IS NOT NULL AND {_since()}
                UNION ALL
                SELECT 'job parse (started -> ready/failed)',
                    {stat(v=_MS.format(end="parse_finished_at", start="parse_started_at"))}
                    FROM jobs WHERE parse_finished_at IS NOT NULL AND {_since()}""",
                days,
            ),
        )
    )
    s.append(
        Section(
            "Model calls",
            "llm_calls.latency_ms per attempt; provider 'manual' = time a person took to answer",
            ["provider", "purpose", "status", "n", "p50 ms", "p95 ms", "max ms", "cache hits"],
            await _rows(
                session,
                f"""SELECT provider, purpose, status, {stat(v="latency_ms")},
                    count(*) FILTER (WHERE cache_hit)
                FROM llm_calls WHERE {_since()}
                GROUP BY provider, purpose, status ORDER BY provider, purpose, status""",
                days,
            ),
        )
    )
    steps = ["extract_resume_ms", "jd_parse_ms", "redact_ms", "evaluate_ms", "score_ms"]
    steps += ["save_ms", "total_ms"]
    step_sql = " UNION ALL ".join(
        f"""SELECT '{step}', status,
            {stat(v=f"(timings->>'{step}')::int")}
            FROM scoring_runs WHERE timings ? '{step}' AND {_since()} GROUP BY status"""
        for step in steps
    )
    s.append(
        Section(
            "Resume scoring: steps of each run",
            "scoring_runs.timings; failed runs keep the time spent up to the failure",
            ["step", "status", "n", "p50 ms", "p95 ms", "max ms"],
            await _rows(session, step_sql, days),
        )
    )
    s.append(
        Section(
            "Resume scoring: queue",
            "job_candidates: waiting for a worker, then being scored (incl. model wait)",
            ["measure", "n", "p50 ms", "p95 ms", "max ms"],
            await _rows(
                session,
                f"""SELECT 'queue wait', {stat(v=_MS.format(end="started_at", start="queued_at"))}
                    FROM job_candidates WHERE started_at IS NOT NULL AND {_since("queued_at")}
                UNION ALL
                SELECT 'scoring', {stat(v=_MS.format(end="finished_at", start="started_at"))}
                    FROM job_candidates WHERE finished_at IS NOT NULL AND {_since("queued_at")}
                UNION ALL
                SELECT 'end to end', {stat(v=_MS.format(end="finished_at", start="queued_at"))}
                    FROM job_candidates WHERE finished_at IS NOT NULL AND {_since("queued_at")}
                """,
                days,
            ),
        )
    )
    s.append(
        Section(
            "Outcomes",
            "failed runs by reason; candidates needing more than one attempt",
            ["what", "code", "count"],
            await _rows(
                session,
                f"""SELECT 'failed run', coalesce(error_code, '?'), count(*) FROM scoring_runs
                    WHERE status = 'failed' AND {_since()} GROUP BY error_code
                UNION ALL
                SELECT 'still working', status, count(*) FROM scoring_runs
                    WHERE status NOT IN ('completed', 'failed') AND {_since()} GROUP BY status
                UNION ALL
                SELECT 'candidate attempts > 1', '', count(*) FROM job_candidates
                    WHERE attempts > 1 AND {_since("queued_at")}
                ORDER BY 1, 3 DESC""",
                days,
            ),
        )
    )
    s.append(
        Section(
            "Search",
            "search_events; zero-hit searches show what recruiters look for but don't have",
            ["n", "p50 ms", "p95 ms", "max ms", "avg hits", "zero-hit %", "top match p50"],
            await _rows(
                session,
                f"""SELECT {stat(v="duration_ms")}, round(avg(hit_count), 1),
                    round(100.0 * count(*) FILTER (WHERE hit_count = 0) / nullif(count(*), 0)),
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY top_match)
                FROM search_events WHERE {_since()}""",
                days,
            ),
        )
    )
    s.append(
        Section(
            "Slowest searches",
            "query start, terms, database size",
            ["query", "terms", "resumes", "hits", "ms"],
            await _rows(
                session,
                f"""SELECT left(regexp_replace(query, '\\s+', ' ', 'g'), 50), term_count,
                    total_candidates, hit_count, duration_ms
                FROM search_events WHERE {_since()} ORDER BY duration_ms DESC LIMIT 5""",
                days,
            ),
        )
    )
    return s


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool | str):
        return str(value)
    if isinstance(value, int | float | Decimal):
        number = float(value)
        # Small values keep one decimal (e.g. 9.5 hits, 31.3 ms); the rest are whole.
        if abs(number) < 100 and number % 1:
            return f"{number:.1f}"
        return f"{number:,.0f}"
    return str(value)


def render(sections: list[Section], days: int) -> str:
    out = [f"Timings for the last {days} days (all times in milliseconds)"]
    for section in sections:
        out += ["", f"== {section.title}", f"   {section.note}"]
        cells = [section.columns] + [[_cell(v) for v in row] for row in section.rows]
        if len(cells) == 1:
            out.append("   (no data)")
            continue
        widths = [max(len(r[i]) for r in cells) for i in range(len(section.columns))]
        for i, row in enumerate(cells):
            line = "  ".join(
                v.ljust(w) if j < 2 or not v[:1].isdigit() else v.rjust(w)
                for j, (v, w) in enumerate(zip(row, widths, strict=True))
            )
            out.append("   " + line.rstrip())
            if i == 0:
                out.append("   " + "  ".join("-" * w for w in widths))
    return "\n".join(out)
