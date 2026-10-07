"""Synthetic uptime monitor sederhana; tidak menyimpan token dalam log."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import os


def probe(target: dict, timeout: float) -> dict:
    started = time.perf_counter()
    status = None
    error = None
    try:
        request = Request(target["url"], headers={"User-Agent": "cloud-notes-lab-monitor/1.0"})
        with urlopen(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
        error = "HTTPError"
    except (URLError, TimeoutError, OSError) as exc:
        error = type(exc).__name__
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": target["name"],
        "ok": status is not None and 200 <= status < 400,
        "status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "error": error,
    }


def send_discord(name: str, status: int | None) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return
    payload = json.dumps({"content": f"Cloud Notes lab: {name} gagal dua kali berturut-turut (HTTP {status})."}).encode()
    request = Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=5):
            pass
    except (URLError, TimeoutError, OSError):
        print("Webhook gagal dikirim; URL tetap dirahasiakan.")


def load_targets(path: Path) -> list[dict]:
    """Tolak konfigurasi kosong, duplikat, atau URL yang membawa credential."""
    targets = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets harus berupa daftar yang tidak kosong")
    names = set()
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get("name"), str) or not target["name"].strip():
            raise ValueError("setiap target membutuhkan name")
        if target["name"] in names:
            raise ValueError(f'nama target duplikat: {target["name"]}')
        names.add(target["name"])
        if not isinstance(target.get("url"), str):
            raise ValueError(f'URL target {target["name"]} tidak valid')
        url = urlsplit(target["url"])
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError(f'URL target {target["name"]} harus HTTP(S) tanpa credential/fragment')
    return targets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=Path, default=Path(__file__).with_name("targets.local.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("observations.jsonl"))
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=4)
    parser.add_argument("--reset", action="store_true", help="mulai berkas observasi baru; tanpa opsi ini hasil ditambahkan")
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0 or args.timeout <= 0:
        parser.error("count >= 1, interval >= 0, timeout > 0 diperlukan")
    try:
        targets = load_targets(args.targets)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    failures = {target["name"]: 0 for target in targets}
    alerted = set()
    with args.output.open("w" if args.reset else "a", encoding="utf-8") as stream:
        for index in range(args.count):
            for target in targets:
                row = probe(target, args.timeout)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(f'{row["name"]}: {"UP" if row["ok"] else "DOWN"} ({row["latency_ms"]} ms)')
                if row["ok"]:
                    failures[target["name"]] = 0
                    alerted.discard(target["name"])
                else:
                    failures[target["name"]] += 1
                    if failures[target["name"]] >= 2 and target["name"] not in alerted:
                        send_discord(target["name"], row["status"])
                        alerted.add(target["name"])
            if index < args.count - 1:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
