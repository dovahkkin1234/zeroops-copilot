#!/usr/bin/env python3
"""
Stack Overflow duplicate-question retrieval evaluation.

For each (duplicate, original) pair from SO's own duplicate-close ground
truth, ask: does cosine similarity of error-text embeddings retrieve the
correct original in top-k?

Metrics:  recall@1  recall@3  MRR (mean reciprocal rank)
Compare:  raw text  vs  normalised error-signature (strips paths / line numbers)

This directly validates the memory system's core claim — specifically
whether the normalization in src/zeroops/memory/embeddings.py improves
retrieval over raw text on real community-sourced data.

Attribution: Stack Overflow content © Stack Exchange Inc, CC BY-SA 4.0
  https://stackoverflow.com/help/licensing

Usage:
    uv run python -m eval.so_eval
    uv run python -m eval.so_eval --n-pairs 300
    uv run python -m eval.so_eval --n-pairs 300 --api-key YOUR_KEY
    uv run python -m eval.so_eval --dry-run      # use cached data only
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import requests

# ── project imports ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from zeroops.memory.embeddings import embed, normalize_error_signature

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
CACHE_DIR = ROOT / "eval" / "so_data"
OUT_DIR   = ROOT / "eval" / "results"
SO_API    = "https://api.stackexchange.com/2.3"


# ── helpers ───────────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    """Remove HTML tags; collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _so_get(url: str, params: dict, api_key: str = "") -> dict:
    """HTTP GET with backoff-respect and rate-limit handling."""
    if api_key:
        params = {**params, "key": api_key}
    while True:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 429:
            print("[rate-limit] sleeping 15s …", flush=True)
            time.sleep(15)
            continue
        if resp.status_code in (400, 404):
            # SO returns 400 when paging beyond available results
            return {"items": [], "has_more": False}
        resp.raise_for_status()
        data = resp.json()
        backoff = data.get("backoff", 0)
        if backoff:
            print(f"[backoff] SO asked us to wait {backoff}s", flush=True)
            time.sleep(backoff + 0.5)
        return data


# ── filter creation ───────────────────────────────────────────────────────────

def get_so_filter(api_key: str = "") -> str:
    """
    Create (once) and cache a Stack Exchange filter that includes
    question.body and question.closed_details.
    """
    cache = CACHE_DIR / "filter.txt"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        return cache.read_text(encoding="utf-8").strip()

    try:
        data = _so_get(
            f"{SO_API}/filters/create",
            {
                "base":    "default",
                "include": "question.body;question.closed_reason;question.closed_details",
            },
        )
        flt = data["items"][0]["filter"]
        cache.write_text(flt, encoding="utf-8")
        print(f"[filter] created SO filter: {flt}")
        return flt
    except Exception as exc:
        print(f"[warn] filter creation failed ({exc}); using 'withbody' fallback")
        return "withbody"


# ── data fetching ─────────────────────────────────────────────────────────────

def fetch_pairs(n: int, api_key: str = "", dry_run: bool = False) -> list[dict]:
    """
    Fetch up to n (duplicate, original) Python question pairs from Stack Overflow.

    Uses SO's own duplicate-close mechanism as ground truth.
    Results are cached under eval/so_data/pairs_{n}.json — re-run is instant.

    Each returned dict has keys:
        dup_id, dup_title, dup_text, orig_id, orig_title, orig_text
    """
    cache = CACHE_DIR / f"pairs_{n}.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache.exists():
        try:
            pairs = json.loads(cache.read_text(encoding="utf-8"))
            if pairs:
                print(f"[cache] loaded {len(pairs)} pairs from {cache.name}")
                return pairs
        except (json.JSONDecodeError, ValueError):
            pass
        cache.unlink()  # delete empty / corrupt cache; re-fetch

    if dry_run:
        print("[dry-run] no cache found and --dry-run is set; nothing to evaluate")
        sys.exit(0)

    flt  = get_so_filter(api_key)
    raw: list[dict] = []

    print(f"[fetch] collecting duplicate Python questions (target={n}) …")

    for page in range(1, 30):
        data = _so_get(
            f"{SO_API}/questions",
            {
                "tagged":   "python",
                "site":     "stackoverflow",
                "pagesize": 100,
                "order":    "desc",
                "sort":     "votes",
                "filter":   flt,
                "page":     page,
            },
            api_key,
        )
        quota = data.get("quota_remaining", "?")
        found_this_page = 0

        for q in data.get("items", []):
            closed  = (q.get("closed_reason") or "").lower()
            cd      = q.get("closed_details") or {}
            orig_qs = cd.get("original_questions") or []

            if "duplicate" not in closed and not orig_qs:
                continue

            if not orig_qs:
                continue  # have label but no link; skip

            orig_id  = orig_qs[0].get("id") or orig_qs[0].get("question_id")
            if not orig_id:
                continue

            body = strip_html(q.get("body") or "")
            raw.append({
                "dup_id":    q["question_id"],
                "dup_title": q.get("title", ""),
                "dup_body":  body[:3000],
                "orig_id":   int(orig_id),
            })
            found_this_page += 1

        print(f"  page {page:>3}  quota={quota:>6}  "
              f"found_this_page={found_this_page:>3}  total={len(raw):>4}",
              flush=True)

        if len(raw) >= n - 5 or not data.get("has_more"):
            break

        time.sleep(0.4)

    raw = raw[:n]
    if not raw:
        print("[error] no duplicate questions found — the custom filter may not "
              "include closed_details on this key/IP. Try registering a free API "
              "key at https://stackapps.com and passing --api-key")
        sys.exit(1)

    # ── fetch original question bodies ────────────────────────────────────────
    orig_ids = list({p["orig_id"] for p in raw})
    print(f"[fetch] fetching {len(orig_ids)} unique original questions …")
    originals: dict[int, dict] = {}

    for i in range(0, len(orig_ids), 100):
        batch = ";".join(str(x) for x in orig_ids[i : i + 100])
        data = _so_get(
            f"{SO_API}/questions/{batch}",
            {"site": "stackoverflow", "filter": flt},
            api_key,
        )
        for q in data.get("items", []):
            originals[q["question_id"]] = {
                "title": q.get("title", ""),
                "body":  strip_html(q.get("body") or "")[:3000],
            }
        time.sleep(0.4)

    # ── merge ─────────────────────────────────────────────────────────────────
    pairs: list[dict] = []
    for p in raw:
        orig = originals.get(p["orig_id"])
        if not orig:
            continue
        pairs.append({
            "dup_id":    p["dup_id"],
            "dup_title": p["dup_title"],
            "dup_text":  p["dup_title"] + "\n" + p["dup_body"],
            "orig_id":   p["orig_id"],
            "orig_title": orig["title"],
            "orig_text":  orig["title"] + "\n" + orig["body"],
        })

    cache.write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fetch] cached {len(pairs)} usable pairs → {cache}")
    return pairs


# ── retrieval evaluation ──────────────────────────────────────────────────────

def _norm(m: np.ndarray) -> np.ndarray:
    """L2-normalise rows of a matrix."""
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.maximum(norms, 1e-8)


def run_eval(pairs: list[dict], condition: str = "raw") -> dict:
    """
    Build an index from unique originals; query with duplicate texts.

    condition: "raw" uses raw text; "normalized" applies normalize_error_signature
               (strips paths, line numbers, memory addresses) before embedding.
    """
    print(f"\n[eval] condition={condition!r}  pairs={len(pairs)}", flush=True)

    def prepare(text: str) -> str:
        return normalize_error_signature(text) if condition == "normalized" else text

    # ── embed originals (deduplicated) ────────────────────────────────────────
    seen_orig: dict[int, int] = {}   # orig_id → index in orig_ids list
    orig_ids:  list[int]      = []
    orig_embs: list[np.ndarray] = []

    for p in pairs:
        if p["orig_id"] not in seen_orig:
            seen_orig[p["orig_id"]] = len(orig_ids)
            orig_ids.append(p["orig_id"])
            orig_embs.append(embed(prepare(p["orig_text"])))

        if len(orig_ids) % 25 == 0:
            print(f"  embedded {len(orig_ids)} originals …", flush=True)

    print(f"  {len(orig_ids)} unique originals in index", flush=True)
    index = _norm(np.stack(orig_embs))  # (N_orig, dim)

    # ── embed duplicates and score ────────────────────────────────────────────
    hits1 = hits3 = 0
    rr_sum = 0.0

    for i, p in enumerate(pairs):
        q_emb  = embed(prepare(p["dup_text"]))
        q_norm = q_emb / max(np.linalg.norm(q_emb), 1e-8)
        sims   = index @ q_norm                     # cosine sim for each original
        ranked = list(np.argsort(-sims))             # descending
        try:
            rank = ranked.index(seen_orig[p["orig_id"]]) + 1  # 1-based
        except (ValueError, KeyError):
            rank = len(ranked) + 1

        if rank == 1: hits1 += 1
        if rank <= 3: hits3 += 1
        rr_sum += 1.0 / rank

        if (i + 1) % 50 == 0:
            print(f"  scored {i + 1}/{len(pairs)} queries …", flush=True)

    n = len(pairs)
    return {
        "condition":  condition,
        "n_pairs":    n,
        "n_originals_in_index": len(orig_ids),
        "recall@1":   round(hits1 / n, 4),
        "recall@3":   round(hits3 / n, 4),
        "mrr":        round(rr_sum / n, 4),
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-pairs",  type=int,  default=300,
                    help="target number of duplicate pairs (default 300)")
    ap.add_argument("--api-key",  default="",
                    help="Stack Exchange API key — raises quota from 300 to "
                         "10 000 req/day. Register free at https://stackapps.com")
    ap.add_argument("--dry-run",  action="store_true",
                    help="use cached data only; exit if cache is missing")
    args = ap.parse_args()

    pairs = fetch_pairs(args.n_pairs, args.api_key, args.dry_run)
    if not pairs:
        print("[error] empty pair list")
        sys.exit(1)

    res_raw  = run_eval(pairs, "raw")
    res_norm = run_eval(pairs, "normalized")

    # ── pretty-print ──────────────────────────────────────────────────────────
    w = 50
    print("\n" + "═" * w)
    print(f"{'SO duplicate retrieval evaluation':^{w}}")
    print("═" * w)
    print(f"  pairs evaluated  : {len(pairs)}")
    print(f"  unique originals : {res_raw['n_originals_in_index']}")
    print(f"  embed model      : all-MiniLM-L6-v2")
    print(f"  source           : Stack Overflow (CC BY-SA 4.0)")
    print("─" * w)
    print(f"  {'condition':<20}  {'R@1':>5}  {'R@3':>5}  {'MRR':>5}")
    print("─" * w)
    print(f"  {'raw text':<20}  "
          f"{res_raw['recall@1']:>5.3f}  "
          f"{res_raw['recall@3']:>5.3f}  "
          f"{res_raw['mrr']:>5.3f}")
    print(f"  {'normalized sig':<20}  "
          f"{res_norm['recall@1']:>5.3f}  "
          f"{res_norm['recall@3']:>5.3f}  "
          f"{res_norm['mrr']:>5.3f}")
    print("═" * w)

    delta_r1  = res_norm["recall@1"] - res_raw["recall@1"]
    delta_mrr = res_norm["mrr"]      - res_raw["mrr"]
    sign_r1   = "+" if delta_r1  >= 0 else ""
    sign_mrr  = "+" if delta_mrr >= 0 else ""
    print(f"  normalisation Δ  :  R@1 {sign_r1}{delta_r1:+.3f}   MRR {sign_mrr}{delta_mrr:+.3f}")
    print("═" * w + "\n")

    # ── save results ──────────────────────────────────────────────────────────
    ts  = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / ts
    out.mkdir(parents=True, exist_ok=True)

    result_obj = {
        "timestamp":   ts,
        "experiment":  "so_duplicate_retrieval",
        "source":      "Stack Overflow (CC BY-SA 4.0)",
        "embed_model": "all-MiniLM-L6-v2",
        "n_pairs":     len(pairs),
        "results":     [res_raw, res_norm],
        "notes": (
            "Ground truth: SO's own duplicate-close mechanism. "
            "Query = duplicate question text; relevant = its linked original. "
            "'normalized' condition applies normalize_error_signature() from "
            "src/zeroops/memory/embeddings.py before embedding."
        ),
    }
    out_path = out / "so_eval.json"
    out_path.write_text(json.dumps(result_obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
