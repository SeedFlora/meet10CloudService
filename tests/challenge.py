"""Uji lokal deterministik monitor/status, tanpa akun dan tanpa service lab lain."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor import load_targets, probe  # noqa: E402
from report import summarize  # noqa: E402
from status import render  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503 if self.path == "/down" else 200)
        self.end_headers()
        self.wfile.write(b"lab10-check")

    def log_message(self, *_args):
        pass


checks = 0


def check(label, condition):
    global checks
    if not condition:
        raise AssertionError(label)
    checks += 1
    print("PASS", label)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    base = f"http://127.0.0.1:{server.server_port}"
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        targets = temp / "targets.json"
        targets.write_text(json.dumps([{"name": "Sehat", "url": base + "/ok"},
                                       {"name": "Gangguan", "url": base + "/down"}]), encoding="utf-8")
        observations = temp / "observations.jsonl"
        html = temp / "status.html"
        check("konfigurasi dua target valid", len(load_targets(targets)) == 2)
        check("probe sehat menghasilkan HTTP 200", probe({"name": "Sehat", "url": base + "/ok"}, 2)["ok"])
        down = probe({"name": "Gangguan", "url": base + "/down"}, 2)
        check("HTTP 503 dihitung DOWN", not down["ok"] and down["status"] == 503)
        cmd = [sys.executable, "-B", str(ROOT / "monitor.py"), "--targets", str(targets),
               "--output", str(observations), "--count", "2", "--interval", "0", "--reset"]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        rows = summarize(observations)
        check("dua putaran menghasilkan empat observasi", sum(row["checks"] for row in rows) == 4)
        check("availability UP dan DOWN akurat", rows[0]["availability_pct"] == 0 and rows[1]["availability_pct"] == 100)
        check("budget negatif menunjukkan target melampaui SLO", rows[0]["budget_exhausted"] and rows[0]["error_budget_checks"] < 0)
        subprocess.run([sys.executable, "-B", str(ROOT / "status.py"), "--input", str(observations),
                        "--output", str(html)], check=True, capture_output=True, text=True)
        content = html.read_text(encoding="utf-8")
        check("status web memuat UP dan DOWN", "UP" in content and "DOWN" in content)
        check("nama target di-escape pada HTML", "&lt;script&gt;" in render([{"name": "<script>", "last_ok": True,
              "p95_latency_ms": 1, "availability_pct": 100, "up": 1, "checks": 1, "error_budget_checks": 0.01}]))
        targets.write_text(json.dumps([{"name": "duplikat", "url": base}, {"name": "duplikat", "url": base}]), encoding="utf-8")
        try:
            load_targets(targets)
        except ValueError:
            check("nama target duplikat ditolak", True)
        else:
            raise AssertionError("nama target duplikat diterima")
        print(f"challenge: {checks} PASS, 0 FAIL")
finally:
    server.shutdown()
    server.server_close()
