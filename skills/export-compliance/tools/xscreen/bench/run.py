"""Benchmark runner and baseline comparison.

    python3 -m xscreen.bench.run --seed 7 --size 5000
    python3 -m xscreen.bench.run --seed 7 --size 5000 --json out.json
    python3 -m xscreen.bench.run --seed 7 --size 5000 --baseline out.json

The JSON result is emitted with sorted keys so two runs on the same seed and
size differ only under `timing`. `comparable()` strips that section for the
determinism test and for baseline diffs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from typing import Any

from ..match import ListIndex, screen_name, tuning_digest
from ..models import SCHEMA_VERSION, SubjectParty, stable_digest
from .generate import NEGATIVE_CLASSES, Corpus, generate_corpus
from .perturb import CLASS_ORDER, perturb_all

BENCH_VERSION = "1.0.0"
BANDS: tuple[str, ...] = ("EXACT", "STRONG", "WEAK")
_ORDER = {"EXACT": 3, "STRONG": 2, "WEAK": 1, "NONE": 0}


def _pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def _distribution(counts: list[int]) -> dict[str, Any]:
    s = sorted(counts)
    hist = Counter()
    for c in counts:
        hist["0" if c == 0 else "1" if c == 1 else "2-5" if c <= 5 else "6-20" if c <= 20 else "21+"] += 1
    return {
        "n": len(counts),
        "mean": round(sum(counts) / len(counts), 3) if counts else 0.0,
        "p50": _percentile(s, 0.5),
        "p90": _percentile(s, 0.9),
        "p99": _percentile(s, 0.99),
        "max": s[-1] if s else 0,
        "histogram": {k: hist.get(k, 0) for k in ("0", "1", "2-5", "6-20", "21+")},
    }


def _timing(ms: list[float]) -> dict[str, float]:
    s = sorted(ms)
    return {
        "ms_per_subject_mean": round(sum(ms) / len(ms), 3) if ms else 0.0,
        "ms_per_subject_p50": round(_percentile(s, 0.5), 3),
        "ms_per_subject_p95": round(_percentile(s, 0.95), 3),
        "ms_per_subject_max": round(s[-1], 3) if s else 0.0,
    }


def run_benchmark(seed: int = 7, size: int = 5000, negatives: int | None = None,
                  examples: int = 5, classes: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Generate, index, screen, and score. Returns the full result dict."""
    t0 = time.perf_counter()
    corpus: Corpus = generate_corpus(seed, size, negatives)
    t_gen = time.perf_counter() - t0

    t0 = time.perf_counter()
    index = ListIndex()
    index.add_all(corpus.listed())
    index.build()
    t_build = time.perf_counter() - t0

    positives = perturb_all(corpus.targets, seed, classes)

    # --- positives -------------------------------------------------------
    per_class: dict[str, dict[str, Any]] = {}
    pos_cands: list[int] = []
    pos_ms: list[float] = []
    for i, ps in enumerate(positives):
        subj = SubjectParty(ref=f"p{i}", name=ps.name)
        t = time.perf_counter()
        cands = screen_name(subj, index)
        pos_ms.append((time.perf_counter() - t) * 1000.0)
        pos_cands.append(len(cands))
        band = "NONE"
        for c in cands:
            if c.listed_uid == ps.listed_uid:
                band = c.band
                break
        row = per_class.setdefault(ps.cls, {
            "n": 0, "EXACT": 0, "STRONG": 0, "WEAK": 0, "NONE": 0, "misses": [],
            "missed_at_blocking": 0, "missed_at_scoring": 0,
            "by_kind": {}, "by_style": {},
        })
        row["n"] += 1
        row[band] += 1
        bk = row["by_kind"].setdefault(ps.kind, {"n": 0, "found_weak": 0})
        bk["n"] += 1
        bs = row["by_style"].setdefault(ps.style, {"n": 0, "found_weak": 0})
        bs["n"] += 1
        if band != "NONE":
            bk["found_weak"] += 1
            bs["found_weak"] += 1
        else:
            # Where did the miss happen? If blocking never pulled the true
            # party into scoring, no weight change can recover it -- that is
            # an index/blocking gap. If it was scored and fell below the
            # floor, it is a weights/threshold question. Maintainers need
            # the two told apart.
            blocked = index.block(ps.name).entries
            reached = any(index.entries[j].uid == ps.listed_uid for j in blocked)
            stage = "scoring" if reached else "blocking"
            row[f"missed_at_{stage}"] += 1
            if len(row["misses"]) < examples:
                row["misses"].append({"subject": ps.name, "listed": ps.listed_name,
                                      "uid": ps.listed_uid, "kind": ps.kind, "style": ps.style,
                                      "missed_at": stage, "candidates_returned": len(cands)})

    recall_by_class: dict[str, Any] = {}
    tot = {"n": 0, "EXACT": 0, "STRONG": 0, "WEAK": 0}
    for cls in (classes or CLASS_ORDER):
        r = per_class.get(cls)
        if r is None:
            continue
        n = r["n"]
        ge_exact = r["EXACT"]
        ge_strong = ge_exact + r["STRONG"]
        ge_weak = ge_strong + r["WEAK"]
        tot["n"] += n
        tot["EXACT"] += ge_exact
        tot["STRONG"] += ge_strong
        tot["WEAK"] += ge_weak
        recall_by_class[cls] = {
            "n": n,
            "found_exact": ge_exact,
            "found_strong": ge_strong,
            "found_weak": ge_weak,
            "missed": n - ge_weak,
            "missed_at_blocking": r["missed_at_blocking"],
            "missed_at_scoring": r["missed_at_scoring"],
            "recall_exact": _pct(ge_exact, n),
            "recall_strong": _pct(ge_strong, n),
            "recall_weak": _pct(ge_weak, n),
            "recall_weak_by_kind": {k: _pct(v["found_weak"], v["n"]) for k, v in sorted(r["by_kind"].items())},
            "recall_weak_by_style": {k: _pct(v["found_weak"], v["n"]) for k, v in sorted(r["by_style"].items())},
            "misses": r["misses"],
        }
    macro = [v["recall_weak"] for k, v in recall_by_class.items() if k != "identity"]
    overall = {
        "n": tot["n"],
        "recall_exact": _pct(tot["EXACT"], tot["n"]),
        "recall_strong": _pct(tot["STRONG"], tot["n"]),
        "recall_weak": _pct(tot["WEAK"], tot["n"]),
        "macro_recall_weak_excluding_identity": round(sum(macro) / len(macro), 4) if macro else 0.0,
    }

    # --- negatives -------------------------------------------------------
    neg_class: dict[str, dict[str, Any]] = {}
    neg_cands: list[int] = []
    neg_ms: list[float] = []
    for i, ng in enumerate(corpus.negatives):
        subj = SubjectParty(ref=f"n{i}", name=ng.name)
        t = time.perf_counter()
        cands = screen_name(subj, index)
        neg_ms.append((time.perf_counter() - t) * 1000.0)
        neg_cands.append(len(cands))
        top = max((_ORDER[c.band] for c in cands), default=0)
        row = neg_class.setdefault(ng.cls, {"n": 0, "fp_weak": 0, "fp_strong": 0, "fp_exact": 0,
                                            "examples": []})
        row["n"] += 1
        if top >= 1:
            row["fp_weak"] += 1
        if top >= 2:
            row["fp_strong"] += 1
        if top >= 3:
            row["fp_exact"] += 1
        if top >= 1 and len(row["examples"]) < examples:
            best = cands[0]
            row["examples"].append({"subject": ng.name, "matched": best.listed_name,
                                    "band": best.band, "score": best.score,
                                    "shaped_after": ng.shaped_after})
    fp_by_class: dict[str, Any] = {}
    ntot = {"n": 0, "fp_weak": 0, "fp_strong": 0, "fp_exact": 0}
    for cls in NEGATIVE_CLASSES:
        r = neg_class.get(cls)
        if r is None:
            continue
        for k in ntot:
            ntot[k] += r[k]
        fp_by_class[cls] = {
            "n": r["n"], "fp_weak": r["fp_weak"], "fp_strong": r["fp_strong"], "fp_exact": r["fp_exact"],
            "fp_rate_weak": _pct(r["fp_weak"], r["n"]),
            "fp_rate_strong": _pct(r["fp_strong"], r["n"]),
            "fp_rate_exact": _pct(r["fp_exact"], r["n"]),
            "examples": r["examples"],
        }
    fp_overall = {
        "n": ntot["n"],
        "fp_rate_weak": _pct(ntot["fp_weak"], ntot["n"]),
        "fp_rate_strong": _pct(ntot["fp_strong"], ntot["n"]),
        "fp_rate_exact": _pct(ntot["fp_exact"], ntot["n"]),
    }

    kinds = Counter(b.kind for b in corpus.targets)
    styles = Counter(b.style for b in corpus.targets)
    corpus_digest = stable_digest([p.name for p in corpus.listed()] + [n.name for n in corpus.negatives])
    all_ms = pos_ms + neg_ms
    return {
        "benchmark": {
            "version": BENCH_VERSION,
            "seed": seed,
            "size": size,
            "negatives": len(corpus.negatives),
            "engine_version": SCHEMA_VERSION,
            "tuning_digest": tuning_digest(),
            "corpus_digest": corpus_digest,
        },
        "corpus": {
            "targets": len(corpus.targets),
            "decoys": len(corpus.decoys),
            "index_entries": index.size,
            "targets_by_kind": dict(sorted(kinds.items())),
            "targets_by_style": dict(sorted(styles.items())),
            "positives_screened": len(positives),
            "negatives_screened": len(corpus.negatives),
        },
        "recall": {"by_class": recall_by_class, "overall": overall},
        "false_positives": {"by_class": fp_by_class, "overall": fp_overall},
        "candidates_per_subject": {
            "positives": _distribution(pos_cands),
            "negatives": _distribution(neg_cands),
        },
        "timing": {
            "generate_s": round(t_gen, 3),
            "index_build_s": round(t_build, 3),
            "screen_total_s": round(sum(all_ms) / 1000.0, 3),
            "subjects": len(all_ms),
            **_timing(all_ms),
        },
    }


def comparable(result: dict[str, Any]) -> dict[str, Any]:
    """The result minus everything that legitimately differs between runs."""
    return {k: v for k, v in result.items() if k != "timing"}


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _f(x: float) -> str:
    return f"{x * 100:.1f}%"


def to_markdown(result: dict[str, Any]) -> str:
    b = result["benchmark"]
    c = result["corpus"]
    lines = [
        f"## xscreen benchmark -- seed {b['seed']}, size {b['size']}",
        "",
        f"Engine {b['engine_version']}, tuning digest `{b['tuning_digest'][:12]}`, "
        f"corpus digest `{b['corpus_digest'][:12]}`, bench {b['version']}.",
        f"Index: {c['targets']} targets + {c['decoys']} decoys = {c['index_entries']} entries. "
        f"Screened {c['positives_screened']} perturbed positives and {c['negatives_screened']} negatives.",
        "",
        "### Recall by perturbation class",
        "",
        "| class | n | >=EXACT | >=STRONG | >=WEAK | missed | at blocking | at scoring |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cls, r in result["recall"]["by_class"].items():
        lines.append(f"| {cls} | {r['n']} | {_f(r['recall_exact'])} | {_f(r['recall_strong'])} | "
                     f"{_f(r['recall_weak'])} | {r['missed']} | {r['missed_at_blocking']} | "
                     f"{r['missed_at_scoring']} |")
    o = result["recall"]["overall"]
    lines += [
        f"| **overall (micro)** | {o['n']} | {_f(o['recall_exact'])} | {_f(o['recall_strong'])} | "
        f"{_f(o['recall_weak'])} | | | |",
        "",
        f"Macro-averaged recall at >=WEAK across classes (identity excluded): "
        f"**{_f(o['macro_recall_weak_excluding_identity'])}**.",
        "",
        "### False-positive rate on negatives",
        "",
        "| negative class | n | FP @>=WEAK | FP @>=STRONG | FP @EXACT |",
        "|---|---:|---:|---:|---:|",
    ]
    for cls, r in result["false_positives"]["by_class"].items():
        lines.append(f"| {cls} | {r['n']} | {_f(r['fp_rate_weak'])} | {_f(r['fp_rate_strong'])} | "
                     f"{_f(r['fp_rate_exact'])} |")
    fo = result["false_positives"]["overall"]
    lines += [
        f"| **overall** | {fo['n']} | {_f(fo['fp_rate_weak'])} | {_f(fo['fp_rate_strong'])} | "
        f"{_f(fo['fp_rate_exact'])} |",
        "",
        "### Candidates per subject",
        "",
        "| subjects | mean | p50 | p90 | p99 | max | 0 | 1 | 2-5 | 6-20 | 21+ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("positives", "negatives"):
        d = result["candidates_per_subject"][label]
        h = d["histogram"]
        lines.append(f"| {label} | {d['mean']} | {d['p50']} | {d['p90']} | {d['p99']} | {d['max']} | "
                     f"{h['0']} | {h['1']} | {h['2-5']} | {h['6-20']} | {h['21+']} |")
    t = result["timing"]
    lines += [
        "",
        "### Timing (this machine; not part of the determinism contract)",
        "",
        f"Index build {t['index_build_s']} s; {t['subjects']} subjects screened in "
        f"{t['screen_total_s']} s; per subject mean {t['ms_per_subject_mean']} ms, "
        f"p50 {t['ms_per_subject_p50']} ms, p95 {t['ms_per_subject_p95']} ms, "
        f"max {t['ms_per_subject_max']} ms.",
        "",
        "### Weakest classes (>=WEAK), with example misses",
        "",
    ]
    ranked = sorted(((r["recall_weak"], cls) for cls, r in result["recall"]["by_class"].items()
                     if cls != "identity"))
    for rec, cls in ranked[:5]:
        r = result["recall"]["by_class"][cls]
        lines.append(f"- **{cls}** {_f(rec)} ({r['missed']}/{r['n']} missed)")
        for m in r["misses"][:3]:
            lines.append(f"  - `{m['subject']}` did not find `{m['listed']}` "
                         f"[{m['kind']}/{m['style']}, lost at {m['missed_at']}]")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------

def compare(current: dict[str, Any], baseline: dict[str, Any],
            tolerance: float = 0.01) -> tuple[str, int]:
    """Diff two results. Returns (report text, exit code).

    Exit 0: no class regressed at >=WEAK beyond `tolerance`.
    Exit 1: at least one class (or the overall figure) regressed.
    Exit 2: the two runs are not comparable (different seed or size).
    """
    cb, bb = current["benchmark"], baseline["benchmark"]
    lines: list[str] = []
    if (cb["seed"], cb["size"], cb.get("negatives")) != (bb["seed"], bb["size"], bb.get("negatives")):
        lines.append(f"NOT COMPARABLE: baseline is seed {bb['seed']} size {bb['size']} "
                     f"negatives {bb.get('negatives')}; current is seed {cb['seed']} size "
                     f"{cb['size']} negatives {cb.get('negatives')}.")
        return "\n".join(lines) + "\n", 2
    if cb.get("corpus_digest") != bb.get("corpus_digest"):
        lines.append("WARNING: corpus digest differs -- the generator changed between runs, "
                     "so per-class deltas mix engine changes with corpus changes.")
    if cb.get("tuning_digest") != bb.get("tuning_digest"):
        lines.append("NOTE: engine tuning digest differs -- matcher constants were changed.")

    lines += ["", "| class | baseline >=WEAK | current >=WEAK | delta | >=STRONG delta | status |",
              "|---|---:|---:|---:|---:|---|"]
    regressed: list[str] = []
    base_classes = baseline["recall"]["by_class"]
    cur_classes = current["recall"]["by_class"]
    for cls, br in base_classes.items():
        cr = cur_classes.get(cls)
        if cr is None:
            lines.append(f"| {cls} | {_f(br['recall_weak'])} | (missing) | | | REGRESSED |")
            regressed.append(f"{cls}: missing from current run")
            continue
        d = cr["recall_weak"] - br["recall_weak"]
        ds = cr["recall_strong"] - br["recall_strong"]
        status = "REGRESSED" if d < -tolerance else ("improved" if d > tolerance else "ok")
        if status == "REGRESSED":
            regressed.append(f"{cls}: {_f(br['recall_weak'])} -> {_f(cr['recall_weak'])}")
        lines.append(f"| {cls} | {_f(br['recall_weak'])} | {_f(cr['recall_weak'])} | "
                     f"{d * 100:+.1f} pp | {ds * 100:+.1f} pp | {status} |")
    for cls in cur_classes:
        if cls not in base_classes:
            lines.append(f"| {cls} | (new) | {_f(cur_classes[cls]['recall_weak'])} | | | new |")
    bo, co = baseline["recall"]["overall"], current["recall"]["overall"]
    d = co["recall_weak"] - bo["recall_weak"]
    status = "REGRESSED" if d < -tolerance else "ok"
    if status == "REGRESSED":
        regressed.append(f"overall: {_f(bo['recall_weak'])} -> {_f(co['recall_weak'])}")
    lines.append(f"| **overall** | {_f(bo['recall_weak'])} | {_f(co['recall_weak'])} | "
                 f"{d * 100:+.1f} pp | | {status} |")

    bf, cf = baseline["false_positives"]["overall"], current["false_positives"]["overall"]
    lines += ["", f"False-positive rate @>=WEAK: {_f(bf['fp_rate_weak'])} -> {_f(cf['fp_rate_weak'])} "
              f"({(cf['fp_rate_weak'] - bf['fp_rate_weak']) * 100:+.1f} pp); "
              f"@>=STRONG: {_f(bf['fp_rate_strong'])} -> {_f(cf['fp_rate_strong'])} "
              f"({(cf['fp_rate_strong'] - bf['fp_rate_strong']) * 100:+.1f} pp)."]
    if cf["fp_rate_weak"] - bf["fp_rate_weak"] > tolerance:
        lines.append("WARNING: false-positive rate at >=WEAK rose beyond tolerance "
                     "(not a failure; recall is the gate).")
    lines.append("")
    if regressed:
        lines.append(f"REGRESSION: {len(regressed)} class(es) lost more than "
                     f"{tolerance * 100:.1f} pp of recall at >=WEAK:")
        lines.extend(f"  - {r}" for r in regressed)
        return "\n".join(lines) + "\n", 1
    lines.append(f"OK: no class regressed beyond {tolerance * 100:.1f} pp.")
    return "\n".join(lines) + "\n", 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m xscreen.bench.run",
        description="Reproducible recall / false-positive benchmark for the xscreen matcher.",
    )
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--size", type=int, default=5000, help="number of listed target parties")
    ap.add_argument("--negatives", type=int, default=None, help="number of negative subjects (default: --size)")
    ap.add_argument("--examples", type=int, default=5, help="example misses / false positives kept per class")
    ap.add_argument("--json", metavar="PATH", help="write the JSON result here ('-' for stdout)")
    ap.add_argument("--markdown", metavar="PATH", help="write the Markdown scorecard here")
    ap.add_argument("--quiet", action="store_true", help="do not print the Markdown scorecard")
    ap.add_argument("--baseline", metavar="PATH", help="compare against a previous JSON result")
    ap.add_argument("--tolerance", type=float, default=0.01,
                    help="max allowed per-class recall drop at >=WEAK before failing (fraction)")
    args = ap.parse_args(argv)

    result = run_benchmark(seed=args.seed, size=args.size, negatives=args.negatives,
                           examples=args.examples)
    md = to_markdown(result)
    if args.json == "-":
        sys.stdout.write(to_json(result))
    elif args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(to_json(result))
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(md)
    if not args.quiet and args.json != "-":
        sys.stdout.write(md)

    if args.baseline:
        with open(args.baseline, encoding="utf-8") as fh:
            baseline = json.load(fh)
        report, code = compare(result, baseline, args.tolerance)
        sys.stdout.write("\n### Baseline comparison\n" + report)
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
