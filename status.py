"""Ekspor status HTML statis dari hasil monitor lokal."""

import argparse
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from report import summarize


def render(rows: list[dict]) -> str:
    cards = []
    for row in rows:
        state = "UP" if row["last_ok"] else "DOWN"
        p95 = "n/a" if row["p95_latency_ms"] is None else f'{row["p95_latency_ms"]} ms'
        cards.append(f'<article><h2>{escape(row["name"])}</h2><strong class="{state.lower()}">{state}</strong>'
                     f'<p>Availability sampel: {row["availability_pct"]}% ({row["up"]}/{row["checks"]})</p>'
                     f'<p>p95 respons sukses: {p95}</p>'
                     f'<p>Sisa budget kegagalan (check): {row["error_budget_checks"]}</p></article>')
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return ('<!doctype html><html lang="id"><meta charset="utf-8"><title>Cloud Notes Status</title>'
            '<style>body{font:16px Arial;max-width:760px;margin:40px auto;padding:0 20px;color:#1b2940}'
            'article{border:1px solid #ccd8e4;border-radius:10px;padding:18px;margin:14px 0}.up{color:green}.down{color:#a21b1b}</style>'
            f'<h1>Cloud Notes — Status</h1><p>Dibuat {generated}. Data berasal dari synthetic check kelas.</p>'
            + ''.join(cards) + '</html>')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("observations.jsonl"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("status.html"))
    args = parser.parse_args()
    args.output.write_text(render(summarize(args.input)), encoding="utf-8")
    print(args.output)
