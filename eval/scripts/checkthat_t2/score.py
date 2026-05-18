"""Score predictions with METEOR (same metric as CheckThat! official scorer)."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import nltk
from nltk.translate.meteor_score import single_meteor_score

for pkg in ("wordnet", "punkt_tab", "omw-1.4"):
    try:
        nltk.data.find(pkg)
    except LookupError:
        nltk.download(pkg, quiet=True)

from nltk.tokenize import word_tokenize  # noqa: E402


def _tokenize(s: str) -> list[str]:
    return word_tokenize(s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--show-examples", type=int, default=0,
                    help="print N qualitative examples per system")
    args = ap.parse_args()

    gold_path = args.predictions.with_suffix(".gold.jsonl")
    gold_by_id = {}
    with open(gold_path, encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            gold_by_id[g["id"]] = g

    by_system: dict[str, list[dict]] = defaultdict(list)
    with open(args.predictions, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_system[r["system"]].append(r)

    print(f"\nDataset: {args.predictions.name}  ({len(gold_by_id)} posts)\n")
    print(f"{'System':<14} {'METEOR':>8} {'N':>5} {'errs':>5} {'avg_lat_s':>10}")
    print("-" * 50)

    summary = []
    for system, rows in sorted(by_system.items()):
        scores = []
        errs = 0
        for r in rows:
            if r["error"]:
                errs += 1
                continue
            gold = gold_by_id[r["id"]]["gold"]
            scores.append(single_meteor_score(_tokenize(gold), _tokenize(r["pred"])))
        avg = sum(scores) / len(scores) if scores else 0.0
        avg_lat = sum(r["latency_s"] for r in rows) / len(rows)
        print(f"{system:<14} {avg:>8.4f} {len(scores):>5} {errs:>5} {avg_lat:>10.2f}")
        summary.append((system, avg, scores, rows))

    if args.show_examples:
        print("\n" + "=" * 70)
        print(f"QUALITATIVE EXAMPLES (first {args.show_examples} per system)")
        print("=" * 70)
        for system, _, _, rows in summary:
            print(f"\n--- {system} ---")
            for r in rows[: args.show_examples]:
                if r["error"]:
                    continue
                g = gold_by_id[r["id"]]
                post_preview = g["post"][:120].replace("\n", " ")
                print(f"\n  POST: {post_preview}{'...' if len(g['post']) > 120 else ''}")
                print(f"  GOLD: {g['gold']}")
                print(f"  PRED: {r['pred']}")


if __name__ == "__main__":
    main()
