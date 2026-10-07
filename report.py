"""Hitung contoh SLI availability dan p95 dari observations.jsonl."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from math import ceil


def summarize(path: Path) -> list[dict]:
    grouped = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            grouped[row["name"]].append(row)
    result = []
    for name, rows in sorted(grouped.items()):
        ok = [row for row in rows if row["ok"]]
        latencies = sorted(row["latency_ms"] for row in ok)
        p95 = latencies[max(0, ceil(0.95 * len(latencies)) - 1)] if latencies else None
        availability = len(ok) / len(rows)
        slo = 0.99
        budget_total = len(rows) * (1 - slo)
        budget_spent = len(rows) - len(ok)
        result.append({
            "name": name,
            "checks": len(rows),
            "up": len(ok),
            "availability_pct": round(availability * 100, 2),
            "p95_latency_ms": p95,
            "slo_pct": slo * 100,
            "error_budget_total_checks": round(budget_total, 3),
            "error_budget_spent_checks": budget_spent,
            "error_budget_checks": round(budget_total - budget_spent, 3),
            "budget_exhausted": budget_spent > budget_total,
            "last_ok": rows[-1]["ok"],
        })
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path(__file__).with_name("observations.jsonl"))
    args = parser.parse_args()
    for row in summarize(args.path):
        print(json.dumps(row, ensure_ascii=False))
