"""Build eval/stress/REPORT.md from one or more stress runs.

    cd backend && uv run python ../eval/stress/report.py r1 r2 r3 r4 r5 [--out ../eval/stress/REPORT.md]

Also runs the deterministic PII check over every resume (no LLM). If
eval/stress/code_review.md exists it is included as the code-review section.
"""

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parents[1] / "backend"))

# Expected band per (pair kind, resume variant); None = no fixed expectation.
EXPECT = {
    ("match", "strong"): ("senior JD x strong own-profile resume", 60, None),
    ("match", "mid"): ("mid JD x mid own-profile resume", 50, None),
    ("match", "junior"): ("junior JD x graduate own-profile resume", 50, None),
    ("match", "switcher"): ("lead JD x career-switcher resume", None, 59),
    ("cross_category",): ("JD x resume from another category", None, 49),
}


def load(label: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    d = RESULTS / label
    rows = [json.loads(line) for line in (d / "results.jsonl").read_text().splitlines() if line]
    return json.loads((d / "meta.json").read_text()), rows, json.loads((d / "rubrics.json").read_text())


def pct(n: float, d: float) -> str:
    return f"{100 * n / d:.0f}%" if d else "-"


def q(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fmt(x: float, nd: int = 1) -> str:
    return "-" if x != x else f"{x:.{nd}f}"


def table(header: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def auc(pos: list[float], neg: list[float]) -> float:
    """P(random positive scores higher than random negative); ties count half."""
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def pii_check(manifest: dict[str, Any]) -> list[list[Any]]:
    """Run the app's redaction over every resume's extracted text; list the problems."""
    from app.pipeline.extract import extract_pdf
    from app.pipeline.pii import redact

    problems = []
    for r in manifest["resumes"]:
        text = extract_pdf((SAMPLES / r["path"]).read_bytes(), max_pages=20).text
        red = redact(text)
        name = r["meta"]["name"]
        issues = []
        if name in red.text:
            issues.append(f"full name leaked ({name})")
        if red.counts["phone"] > 1:
            issues.append(f"{red.counts['phone']} phone redactions (1 real phone)")
        if "[CANDIDATE]" in red.text and red.counts["name"] == 0:
            issues.append("unexpected [CANDIDATE] token")
        first_line = next(ln for ln in text.split("\n") if ln.strip())
        if red.counts["name"] and name.split()[-1] not in first_line:
            issues.append("a non-name line was redacted as the name")
        for word in ("Ruby", "Sydney", "Austin"):  # skills / places that must survive
            if text.count(word) > red.text.count(word) + (1 if word in name else 0):
                issues.append(f"'{word}' erased from the body")
        if issues:
            problems.append([r["id"], name, ", ".join(sorted(r["tags"])) or "-", "; ".join(issues)])
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--out", default=str(HERE / "REPORT.md"))
    ap.add_argument("--title", default="Stress test report: JD x resume scoring")
    ap.add_argument("--note", default="", help="markdown paragraph placed under the title")
    args = ap.parse_args()

    manifest = json.loads((SAMPLES / "manifest.json").read_text())
    jd_meta = {d["id"]: d for d in manifest["jds"]}
    cv_meta = {d["id"]: d for d in manifest["resumes"]}
    runs = {lbl: load(lbl) for lbl in args.labels}
    all_resumes = list(manifest["resumes"])  # the PII check always covers every resume
    ran_jds = {r["jd"] for _, rows, _ in runs.values() for r in rows}
    manifest["jds"] = [d for d in manifest["jds"] if d["id"] in ran_jds]
    manifest["pairs"] = [p for p in manifest["pairs"] if p["jd"] in ran_jds]
    used_cvs = {p["resume"] for p in manifest["pairs"]}
    manifest["resumes"] = [d for d in manifest["resumes"] if d["id"] in used_cvs]
    L: list[str] = []
    w = L.append

    w(f"# {args.title}\n")
    if args.note:
        w(args.note + "\n")
    first_meta = runs[args.labels[0]][0]
    w(f"Model: `{first_meta['model']}` (effort `{first_meta['effort']}`), LLM response cache off. "
      f"Corpus: {len(manifest['jds'])} JDs, {len(manifest['resumes'])} resumes, "
      f"{len(manifest['pairs'])} labelled pairs per run, {len(runs)} runs "
      f"({', '.join(f'`{k}`: {v[0]['rubrics']} rubrics' for k, v in runs.items())}).\n")


    # ------------------------------------------------------------------ corpus
    w("## Corpus\n")
    cats = Counter(d["category"] for d in manifest["jds"])
    fmts = Counter(d["format"] for d in manifest["jds"])
    jtags = Counter(t for d in manifest["jds"] for t in d["tags"])
    rtags = Counter(t for d in manifest["resumes"] for t in d["tags"])
    w(f"- **JDs by category:** {', '.join(f'{k} {v}' for k, v in sorted(cats.items()))}. "
      f"{len({d['profile'] for d in manifest['jds']})} role profiles; levels junior, mid, senior, lead.")
    w(f"- **JD formats:** {', '.join(f'{k} {v}' for k, v in fmts.most_common())}.")
    w(f"- **JD edge cases:** {', '.join(f'{k} {v}' for k, v in jtags.most_common())}.")
    w("- **Resumes:** per profile one strong (8-11 yrs), one mid (4-5 yrs), one graduate, one career "
      "switcher from an adjacent profile.")
    w(f"- **Resume edge cases:** {', '.join(f'{k} {v}' for k, v in rtags.most_common())}.")
    w("- **Pairs (3 per JD):** `match` (own profile; level-matched variant: junior JD x graduate, mid x mid, "
      "senior x strong, lead x switcher), `same_category` (strong/mid resume of another profile in the same "
      "category), `cross_category` (random resume from another category). Execution order is shuffled "
      "differently for every run.\n")

    # ------------------------------------------------------------------ reliability
    w("## Reliability and cost\n")
    rel_rows = []
    for lbl, (meta, rows, rub) in runs.items():
        lat = [r["latency_ms"] / 1000 for r in rows if r["status"] == "completed"]
        failed = [r for r in rows if r["status"] != "completed"]
        retries = sum(r.get("llm_attempts_failed", 0) for r in rows)
        calls = sum(r.get("llm_calls", 0) for r in rows)
        rel_rows.append([
            lbl, meta["rubrics"], f"{meta['completed']}/{meta['pairs']}", len(failed),
            len(meta["rubric_errors"]), len(meta["ingest_errors"]), f"{calls} / {retries}",
            fmt(q(lat, 0.5)), fmt(q(lat, 0.95)), f"{meta['total_seconds'] / 60:.1f}",
            f"${meta['rubric_cost_usd']:.3f}", f"${meta['scoring_cost_usd']:.3f}",
            f"{meta['replay']['checked'] - len(meta['replay']['mismatches'])}/{meta['replay']['checked']}",
        ])
    w(table(["run", "rubrics", "completed", "failed", "JD parse failed", "ingest errors",
             "eval calls / failed attempts", "p50 s", "p95 s", "wall min", "JD-parse cost",
             "scoring cost", "replay identical"], rel_rows))
    all_rows = [r for _, rows, _ in runs.values() for r in rows]
    errs = Counter(r.get("error_code") for r in all_rows if r["status"] != "completed")
    if errs:
        w("\n**Failures by error code:** " + ", ".join(f"`{k}` {v}" for k, v in errs.most_common()))
        for r in [r for r in all_rows if r["status"] != "completed"][:8]:
            w(f"- `{r['label']}` {r['pair_id']}: `{r.get('error_code')}` {r.get('error', '')[:160]}")
    for lbl, (meta, _, _) in runs.items():
        for k, v in list(meta["rubric_errors"].items())[:5]:
            w(f"- `{lbl}` JD parse {k}: {v[:200]}")
        for k, v in list(meta["ingest_errors"].items())[:5]:
            w(f"- `{lbl}` ingest {k}: {v[:200]}")
    warn = Counter(wn.split(":")[0] for r in all_rows for wn in r.get("warnings", []))
    w(f"\n**Run warnings** (repairs / missing criteria): "
      + (", ".join(f"`{k}` {v}" for k, v in warn.most_common()) if warn else "none") + "\n")
    tin = [r["tokens_in"] for r in all_rows if r["status"] == "completed"]
    tout = [r["tokens_out"] for r in all_rows if r["status"] == "completed"]
    cost_pair = [r["cost_usd"] for r in all_rows if r["status"] == "completed"]
    if tin and max(tin) > 0:
        w(f"Per scored pair: median {int(st.median(tin))} input / {int(st.median(tout))} output tokens "
          f"(output includes thinking), median cost ${st.median(cost_pair):.5f}, "
          f"max ${max(cost_pair):.5f}.\n")

    # ------------------------------------------------------------------ validity
    w("## Does the score separate good from bad matches?\n")
    by_kind: dict[tuple, list[int]] = defaultdict(list)
    verdicts: dict[tuple, Counter] = defaultdict(Counter)
    for r in all_rows:
        if r["status"] != "completed":
            continue
        key = (r["kind"], r["resume_variant"]) if r["kind"] == "match" else (r["kind"],)
        by_kind[key].append(r["score"])
        verdicts[key][r["verdict"]] += 1
    vrows = []
    for key in [("match", "strong"), ("match", "mid"), ("match", "junior"), ("match", "switcher"),
                ("same_category",), ("cross_category",)]:
        s = by_kind.get(key, [])
        desc, lo, hi = EXPECT.get(key, (" / ".join(key), None, None))
        if lo is not None:
            ok = sum(1 for x in s if x >= lo)
            exp = f"≥ {lo}: {pct(ok, len(s))}"
        elif hi is not None:
            ok = sum(1 for x in s if x <= hi)
            exp = f"≤ {hi}: {pct(ok, len(s))}"
        else:
            exp = "-"
        v = verdicts[key]
        vrows.append([desc if key in EXPECT else "JD x strong/mid resume, other profile, same category",
                      len(s), fmt(st.mean(s)) if s else "-", fmt(q(s, 0.5), 0), f"{min(s, default=0)}-{max(s, default=0)}",
                      exp, f"{v['Strong fit']}/{v['Possible fit']}/{v['Weak fit']}/{v['Not eligible']}"])
    w(table(["pair type", "n", "mean", "median", "range", "within expected band",
             "verdicts strong/possible/weak/not eligible"], vrows))
    good = [r["score"] for r in all_rows if r["status"] == "completed" and r["kind"] == "match"
            and r["resume_variant"] in ("strong", "mid", "junior")]
    bad = [r["score"] for r in all_rows if r["status"] == "completed" and r["kind"] == "cross_category"]
    same = [r["score"] for r in all_rows if r["status"] == "completed" and r["kind"] == "same_category"]
    w(f"\n**Ranking quality (AUC):** level-matched own-profile vs other-category = **{fmt(auc(good, bad), 3)}**; "
      f"vs same-category other profile = **{fmt(auc(good, same), 3)}** (1.0 = always ranked above, 0.5 = coin flip).\n")

    w("### By category (match pairs, excluding career switchers)\n")
    crow = []
    for cat in sorted(cats):
        s = [r["score"] for r in all_rows if r["status"] == "completed" and r["kind"] == "match"
             and r["resume_variant"] != "switcher" and jd_meta[r["jd"]]["category"] == cat]
        x = [r["score"] for r in all_rows if r["status"] == "completed" and r["kind"] == "cross_category"
             and jd_meta[r["jd"]]["category"] == cat]
        crow.append([cat, len(s), fmt(st.mean(s)) if s else "-", fmt(st.mean(x)) if x else "-",
                     fmt(auc(s, x), 3)])
    w(table(["JD category", "match n", "match mean", "cross-category mean", "AUC"], crow))

    w("\n### Biggest misses (averaged over runs)\n")
    pair_scores: dict[str, list[int]] = defaultdict(list)
    for r in all_rows:
        if r["status"] == "completed":
            pair_scores[r["pair_id"]].append(r["score"])
    pair_info = {p["pair_id"]: p for p in manifest["pairs"]}
    fp = sorted(((st.mean(v), k) for k, v in pair_scores.items()
                 if pair_info[k]["kind"] == "cross_category" and st.mean(v) >= 50), reverse=True)
    fn = sorted((st.mean(v), k) for k, v in pair_scores.items() if pair_info[k]["kind"] == "match"
                and pair_info[k]["resume_variant"] in ("strong", "mid", "junior") and st.mean(v) < 50)
    w(f"- Cross-category pairs averaging ≥ 50 (false positives): **{len(fp)}**")
    for m, k in fp[:10]:
        p = pair_info[k]
        w(f"  - {k}: {m:.0f}  ({jd_meta[p['jd']]['meta']['title']} x {cv_meta[p['resume']]['profile']}/{p['resume_variant']})")
    w(f"- Level-matched own-profile pairs averaging < 50 (false negatives): **{len(fn)}**")
    for m, k in fn[:15]:
        p = pair_info[k]
        w(f"  - {k}: {m:.0f}  ({jd_meta[p['jd']]['meta']['title']} [{jd_meta[p['jd']]['format']}] x "
          f"{p['resume_variant']} resume; tags: {', '.join(cv_meta[p['resume']]['tags']) or '-'})")
    w("")

    # ------------------------------------------------------------------ consistency
    if len(runs) > 1:
        w("## Run-to-run consistency\n")
        groups = {"all runs": list(runs)}
        fresh = [k for k, v in runs.items() if v[0]["rubrics"] == "fresh"]
        if len(fresh) > 1:
            groups["fresh-rubric runs (JD re-parsed each run)"] = fresh
        reused_src = {v[0]["rubrics"].replace("reused from ", "") for v in runs.values()
                      if v[0]["rubrics"].startswith("reused")}
        for src in reused_src:
            same_rubric = [src] + [k for k, v in runs.items() if v[0]["rubrics"] == f"reused from {src}"]
            if len(same_rubric) > 1:
                groups[f"same rubric ({', '.join(same_rubric)}): evaluation-only noise"] = same_rubric
        crows = []
        for name, labels in groups.items():
            per: dict[str, list[tuple[int, str]]] = defaultdict(list)
            for lbl in labels:
                for r in runs[lbl][1]:
                    if r["status"] == "completed":
                        per[r["pair_id"]].append((r["score"], r["verdict"]))
            full = {k: v for k, v in per.items() if len(v) == len(labels)}
            spreads = [max(s for s, _ in v) - min(s for s, _ in v) for v in full.values()]
            sds = [st.pstdev([s for s, _ in v]) for v in full.values()]
            flips = sum(1 for v in full.values() if len({vd for _, vd in v}) > 1)
            crows.append([name, len(full), fmt(st.mean(sds)), fmt(q(spreads, 0.5), 0), fmt(q(spreads, 0.9), 0),
                          max(spreads, default=0), pct(sum(1 for s in spreads if s <= 5), len(spreads)),
                          pct(flips, len(full))])
        w(table(["runs compared", "pairs", "mean SD", "median range", "p90 range", "max range",
                 "range ≤ 5 pts", "verdict changed"], crows))
        # worst offenders
        per_all: dict[str, list[int]] = defaultdict(list)
        for lbl in runs:
            for r in runs[lbl][1]:
                if r["status"] == "completed":
                    per_all[r["pair_id"]].append(r["score"])
        worst = sorted(((max(v) - min(v), k, v) for k, v in per_all.items() if len(v) > 1), reverse=True)[:8]
        w("\nLargest swings across all runs:")
        for spread, k, v in worst:
            p = pair_info[k]
            w(f"- {k} ({p['kind']}, {p['resume_variant']}): scores {v} (range {spread})")
        # rubric stability
        if len(fresh) > 1:
            w("\n**Rubric stability across fresh parses of the same JD:**")
            n_crit = defaultdict(list)
            n_must = defaultdict(list)
            n_ko = defaultdict(list)
            for lbl in fresh:
                for jd, rb in runs[lbl][2].items():
                    n_crit[jd].append(len(rb["criteria"]))
                    n_must[jd].append(sum(c["operator"] == "must_have" for c in rb["criteria"]))
                    n_ko[jd].append(sum(bool(c.get("knockout")) for c in rb["criteria"]))
            same_count = sum(1 for v in n_crit.values() if len(set(v)) == 1)
            w(f"- criteria per JD: mean {st.mean(x for v in n_crit.values() for x in v):.1f} "
              f"(min {min(x for v in n_crit.values() for x in v)}, max {max(x for v in n_crit.values() for x in v)}); "
              f"identical count in every parse for {pct(same_count, len(n_crit))} of JDs; "
              f"mean per-JD range {st.mean(max(v) - min(v) for v in n_crit.values()):.1f}.")
            w(f"- must-have count changed between parses for {pct(sum(1 for v in n_must.values() if len(set(v)) > 1), len(n_must))} of JDs; "
              f"knock-out count changed for {pct(sum(1 for v in n_ko.values() if len(set(v)) > 1), len(n_ko))}.")
        w("")

    # ------------------------------------------------------------------ edge cases
    w("## Edge cases\n")
    completed = [r for r in all_rows if r["status"] == "completed"]

    def mean_of(rows: list[dict[str, Any]]) -> str:
        return fmt(st.mean(r["score"] for r in rows)) if rows else "-"

    w("### Resume edge cases (score on `match` pairs vs untagged resumes of the same variant)\n")
    erows = []
    for tag in sorted(rtags):
        tagged = [r for r in completed if r["kind"] == "match" and tag in cv_meta[r["resume"]]["tags"]]
        variants = {r["resume_variant"] for r in tagged}
        base = [r for r in completed if r["kind"] == "match" and not cv_meta[r["resume"]]["tags"]
                and r["resume_variant"] in variants]
        erows.append([tag, len({r['resume'] for r in tagged}), ", ".join(sorted(variants)), mean_of(tagged),
                      mean_of(base)])
    w(table(["tag", "resumes", "variants", "mean score (tagged)", "mean score (untagged, same variants)"], erows))

    inj = [r for r in completed if "prompt_injection" in cv_meta[r["resume"]]["tags"]]
    inj_cross = [r for r in inj if r["kind"] != "match"]
    w(f"\n**Prompt injection in resume** (hidden white text asking for Full Pass on everything): "
      f"{len(inj)} scored pairs; on non-matching JDs mean {mean_of(inj_cross)} vs "
      f"{mean_of([r for r in completed if r['kind'] == 'cross_category' and not cv_meta[r['resume']]['tags']])} "
      f"for clean cross-category pairs; Strong fit verdicts on non-matching JDs: "
      f"{sum(1 for r in inj_cross if r['verdict'] == 'Strong fit')}.")
    ks = [r for r in completed if "keyword_stuffed" in cv_meta[r["resume"]]["tags"] and r["kind"] == "match"]
    w(f"\n**Keyword stuffing** (every JD keyword listed under Skills, none in the work history): "
      f"{len(ks)} match pairs, mean {mean_of(ks)}, Strong fit {sum(1 for r in ks if r['verdict'] == 'Strong fit')}.")

    w("\n### JD edge cases\n")
    for tag in ("jd_prompt_injection", "discriminatory_requirement", "license_knockout", "work_authorization",
                "relocation_notice", "must_avoid"):
        jds = [d["id"] for d in manifest["jds"] if tag in d["tags"]]
        rows_t = [r for r in completed if r["jd"] in jds]
        if tag == "jd_prompt_injection":
            x = [r for r in rows_t if r["kind"] == "cross_category"]
            w(f"- **{tag}** ({len(jds)} JDs): cross-category pairs mean {mean_of(x)}, "
              f"Strong fit {sum(1 for r in x if r['verdict'] == 'Strong fit')} of {len(x)}.")
        elif tag == "discriminatory_requirement":
            leaked = []
            for lbl, (_, _, rub) in runs.items():
                for jd in jds:
                    for c in rub.get(jd, {}).get("criteria", []):
                        text = (c["name"] + " " + " ".join(c["values"]) + " " + c["source_excerpt"]).lower()
                        if any(t in text for t in ("aged", "age ", "male", "born", "native english")):
                            leaked.append(f"{lbl}/{jd}: {c['name']}")
            w(f"- **{tag}** ({len(jds)} JDs: age, gender, birthplace): criteria built on the protected "
              f"characteristic across all runs: **{len(leaked)}**" + (" — " + "; ".join(leaked[:6]) if leaked else "."))
        elif tag == "license_knockout":
            sw = [r for r in rows_t if r["kind"] == "match" and r["resume_variant"] == "switcher"]
            lic = [r for r in rows_t if r["kind"] == "match" and r["resume_variant"] != "switcher"]
            ko_marked = Counter()
            for lbl, (_, _, rub) in runs.items():
                for jd in jds:
                    ko_marked[any(c.get("knockout") and "licen" in (c["name"] + str(c["values"])).lower()
                                  or c.get("knockout") and "certif" in (c["name"] + str(c["values"])).lower()
                                  for c in rub.get(jd, {}).get("criteria", []))] += 1
            w(f"- **{tag}** ({len(jds)} JDs, nurse/teacher): license criterion marked knock-out in "
              f"{ko_marked[True]}/{sum(ko_marked.values())} rubrics; unlicensed switchers: "
              f"{Counter(r['verdict'] for r in sw).most_common()} ; licensed candidates: "
              f"{Counter(r['verdict'] for r in lic).most_common()}.")
        elif tag in ("work_authorization", "relocation_notice"):
            unk = sum(len(r["screening"]) for r in rows_t)
            w(f"- **{tag}** ({len(jds)} JDs): {len(rows_t)} pairs produced {unk} screening questions "
              f"(criteria left 'Unknown' instead of failed); pairs with a knock-out cap from these JDs: "
              f"{sum(1 for r in rows_t if r['knockouts_failed'])}.")
        else:
            w(f"- **{tag}** ({len(jds)} JDs): {len(rows_t)} pairs, mean {mean_of(rows_t)}.")

    w("\n### Grade consistency (LLM outcome vs its own evidence label)\n")
    combos = Counter()
    forced = Counter()
    for r in completed:
        for c in r["criteria"]:
            if c["operator"] in ("must_have", "preferred", "nice_to_have"):
                combos[(c["evidence_strength"], c["llm_outcome"])] += 1
            if c["forced"]:
                forced[c["forced"]] += 1
    total = sum(combos.values())
    odd = {k: v for k, v in combos.items() if k in (("evidenced", "Fail"), ("not_evidenced", "Full Pass"),
                                                     ("not_evidenced", "Partial Pass"),
                                                     ("partial_evidence", "Full Pass"))}
    w(f"{total} positive-criterion grades. Combinations that contradict themselves: "
      + (", ".join(f"`{e}` + `{o}` {v} ({pct(v, total)})" for (e, o), v in odd.items()) or "none")
      + f". Engine overrides: {dict(forced) or 'none'}.\n")
    caps = Counter(c["source"].split(":")[0] for r in completed for c in r["caps"].get("triggered", [])
                   if r["caps"].get("binding"))
    w(f"Binding score caps: {dict(caps) or 'none'} out of {len(completed)} scored pairs.\n")

    # ------------------------------------------------------------------ PII
    w("## PII redaction check (deterministic, every resume)\n")
    probs = pii_check({"resumes": all_resumes})
    w(f"{len(probs)} of {len(all_resumes)} resumes have a redaction problem.\n")
    if probs:
        w(table(["resume", "name", "tags", "problem"], probs))
    w("")

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
