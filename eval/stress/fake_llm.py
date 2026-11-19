"""Offline stand-in for Claude, served behind the real Anthropic SDK via an httpx2 transport.

Used by `run_stress.py --fake-llm` to exercise everything except the model itself (DB,
storage, extraction, PII redaction, ledger, score math, concurrency) at zero cost.
It is a crude keyword matcher, NOT a quality baseline: its scores say nothing about how
well the real model grades.
"""

import asyncio
import json
import re
from typing import Any

import httpx2

_WORD = re.compile(r"[a-z][a-z0-9+#.]{2,}")
_STOP = frozenset("""and the for with years year experience experienced degree bachelor's bachelor
master's equivalent related field similar strong excellent knowledge using such tools or of in
a an to on at is are be including least plus""".split())
_HEADINGS = {
    "requirements": "must_have", "qualifications": "must_have", "preferred qualifications": "preferred",
    "nice to have": "nice_to_have", "bonus points if you have": "nice_to_have",
}


def _words(text: str) -> set[str]:
    return {w.strip(".") for w in _WORD.findall(text.lower())} - _STOP


def _key(text: str, seen: set[str]) -> str:
    base = "c_" + "_".join(re.findall(r"[a-z0-9]+", text.lower())[:4])[:40] or "c_item"
    key, n = base, 1
    while key in seen:
        n += 1
        key = f"{base}_{n}"
    seen.add(key)
    return key


def _rubric(jd: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in jd.split("\n")]
    items: list[tuple[str, str]] = []
    section = None
    for ln in lines:
        low = ln.lower().rstrip(":")
        if low in _HEADINGS:
            section = _HEADINGS[low]
            continue
        if ln.startswith(("•", "-")) and section:
            items.append((ln[1:].strip(), section))
        elif ln and not ln.startswith(("•", "-")) and len(ln) < 40:
            section = _HEADINGS.get(low, None if low not in ("what you'll do",) else None)
    if not items:  # prose JD: split the "you will bring" sentence
        m = re.search(r"you will bring (.+?)\. It would", jd)
        items = [(x.strip(), "must_have") for x in (m.group(1).split(";") if m else [jd[:150]])]
    seen: set[str] = set()
    criteria = []
    must_count = 0
    for text, op in items[:15]:
        if op == "must_have":
            must_count += 1
            if must_count > 6:
                op = "preferred"
        criteria.append({
            "key": _key(text, seen), "name": text[:120], "attribute": "hard_skills", "operator": op,
            "importance": "high" if op == "must_have" and must_count <= 2 else "normal",
            "values": sorted(_words(text))[:8] or [text[:40]], "source_excerpt": text[:200],
            "knockout": "license" in text.lower() or "certificate" in text.lower(),
            "verify_in_screening": False, "group": "",
        })
    title = next((ln for ln in lines if ln), "Role")[:200]
    return {"title": title, "role_summary": "Offline fake rubric.", "core_requirement": items[0][0][:200],
            "criteria": criteria}


def _evaluation(user: str) -> dict[str, Any]:
    criteria = json.loads(user.split("Rubric criteria (JSON):\n", 1)[1].split("\n\n<resume>", 1)[0])
    resume = _words(user.split("<resume>", 1)[1])
    results, hits = [], []
    for c in criteria:
        want = {w for v in c["values"] for w in _words(v)} or {"zzz"}
        share = len(want & resume) / len(want)
        hits.append(share)
        if c["operator"] in ("must_avoid", "may_avoid"):
            ev, out = ("evidenced", "Fail") if share >= 0.6 else ("not_evidenced", "Full Pass")
        elif share >= 0.6:
            ev, out = "evidenced", "Full Pass"
        elif share >= 0.3:
            ev, out = "partial_evidence", "Partial Pass"
        else:
            ev, out = "not_evidenced", "Fail"
        results.append({"key": c["key"], "candidate_value": f"{share:.0%} keyword overlap",
                        "evidence_strength": ev, "outcome": out, "reasoning": "Offline keyword match."})
    avg = sum(hits) / max(1, len(hits))
    level = "Strong" if avg > 0.6 else "Moderate" if avg > 0.4 else "Weak" if avg > 0.2 else "None"
    core = {"Strong": "Clear", "Moderate": "Partial", "Weak": "Weak", "None": "None"}[level]
    return {"role_overlap": {"level": level, "summary": f"Offline overlap {avg:.0%}."},
            "core_requirement": {"level": core, "summary": "Offline."}, "criteria": results}


def _handler(request: httpx2.Request) -> httpx2.Response:
    body = json.loads(request.content)
    user = body["messages"][0]["content"]
    if "<job_description>" in user:
        jd = user.split("<job_description>", 1)[1].rsplit("</job_description>", 1)[0]
        answer = _rubric(jd)
    else:
        answer = _evaluation(user)
    return httpx2.Response(200, json={
        "id": "msg_offline", "type": "message", "role": "assistant", "model": body["model"],
        "content": [{"type": "text", "text": json.dumps(answer)}], "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": len(json.dumps(body)) // 4, "output_tokens": len(json.dumps(answer)) // 4,
                  "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    })


def transport(latency_s: float = 0.0) -> httpx2.MockTransport:
    """latency_s > 0 simulates model response time (async sleep per call)."""
    if latency_s <= 0:
        return httpx2.MockTransport(_handler)

    async def slow(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(latency_s)
        return _handler(request)

    return httpx2.MockTransport(slow)
