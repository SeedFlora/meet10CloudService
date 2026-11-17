"""Cek otomatis stack monitoring (model API, Prometheus, blackbox, Grafana).

Dari laptop (disarankan, tanpa install apa pun):
    docker compose exec model-api python check_stack.py
    docker compose exec model-api python check_stack.py --drift   # + uji alert drift (~1-2 menit)

Atau dari host bila Python terpasang:
    python model-api/check_stack.py --local
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REQUIRED_METRICS = [
    "http_requests_total", "http_request_duration_seconds_bucket", "process_resident_memory_bytes",
    "model_predictions_total", "model_confidence_bucket", "model_input_drift_psi", "model_feedback_total",
]
RULE_GROUPS = {"layer1-sistem", "layer2-model", "layer3-bisnis", "website"}


def call(url: str, payload: dict | None = None, timeout: float = 10):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
        return json.loads(body) if body.strip().startswith(("{", "[")) else body


def prom_query(prom: str, expr: str) -> list:
    url = f"{prom}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    return call(url)["data"]["result"]


def wait_until(fn, timeout: float, every: float = 3):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(every)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="pakai localhost:8090/9090/3001 dari host")
    ap.add_argument("--drift", action="store_true", help="jalankan simulasi drift dan tunggu alert")
    args = ap.parse_args()
    api, prom, graf = (("http://localhost:8090", "http://localhost:9090", "http://localhost:3001") if args.local
                       else ("http://127.0.0.1:8000", "http://prometheus:9090", "http://grafana:3000"))

    results: list[tuple[bool, str]] = []

    def check(name: str, fn):
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append((ok, name))
        print(f"[{'PASS' if ok else 'FAIL'}] {len(results):>2}. {name} - {detail}", flush=True)

    def c_health():
        r = call(f"{api}/health")
        return r.get("status") == "ok", f"model {r.get('model_version')}"

    def c_predict():
        for text in ("aplikasinya cepat dan mudah dipakai", "pengiriman terlambat dan barang rusak",
                     "paket dikirim hari senin"):
            r = call(f"{api}/predict", {"text": text})
        return {"label", "confidence", "oov_ratio"} <= r.keys(), f"'{text}' -> {r['label']} ({r['confidence']})"

    def c_metrics():
        text = call(f"{api}/metrics")
        missing = [m for m in REQUIRED_METRICS if m not in text]
        return not missing, "metrik 3 layer lengkap" if not missing else f"tidak ada: {missing}"

    def c_prom_ready():
        ready = wait_until(lambda: "Ready" in call(f"{prom}/-/ready"), 30)
        return bool(ready), "Prometheus siap" if ready else "Prometheus belum siap"

    def c_targets():
        def all_up():
            active = call(f"{prom}/api/v1/targets")["data"]["activeTargets"]
            jobs = {t["labels"]["job"]: t["health"] for t in active if t["labels"]["job"] != "web-probe"}
            return jobs if jobs and all(h == "up" for h in jobs.values()) and len(jobs) >= 3 else None
        jobs = wait_until(all_up, 40)
        return bool(jobs), f"up: {sorted(jobs)}" if jobs else "ada target yang belum up (lihat /targets)"

    def c_probe():
        def probes():
            res = prom_query(prom, 'probe_success{job="web-probe"}')
            return res if any(r["metric"].get("lokasi") == "lokal" and r["value"][1] == "1" for r in res) else None
        res = wait_until(probes, 45) or []
        status = ", ".join(f"{r['metric'].get('app')}={'UP' if r['value'][1] == '1' else 'DOWN'}" for r in res)
        return bool(res), status or "probe lokal belum sukses"

    def c_rules():
        groups = call(f"{prom}/api/v1/rules")["data"]["groups"]
        names = {g["name"] for g in groups}
        n_rules = sum(len(g["rules"]) for g in groups)
        return RULE_GROUPS <= names and n_rules >= 7, f"{n_rules} rule di grup {sorted(names)}"

    def c_promql():
        res = wait_until(lambda: prom_query(prom, "sum(model_predictions_total) > 0"), 30)
        return bool(res), f"total prediksi tercatat = {res[0]['value'][1]}" if res else "belum ada data"

    def c_grafana():
        def ready():
            health = call(f"{graf}/api/health")
            return health if health.get("database") == "ok" else None

        health = wait_until(ready, 30)
        return bool(health), f"Grafana {health.get('version')}" if health else "Grafana belum siap"

    def c_dashboard():
        r = call(f"{graf}/api/dashboards/uid/ml-production")
        panels = [p for p in r["dashboard"]["panels"] if p["type"] != "row"]
        return len(panels) >= 15, f"'{r['dashboard']['title']}' ({len(panels)} panel)"

    def c_grafana_query():
        body = {"from": "now-5m", "to": "now", "queries": [{
            "refId": "A", "datasource": {"type": "prometheus", "uid": "prometheus"},
            "expr": 'up{job="model-api"}', "instant": True}]}
        r = call(f"{graf}/api/ds/query", body)
        frames = r["results"]["A"]["frames"]
        value = frames[0]["data"]["values"][1][-1] if frames else None
        return value == 1, f"Grafana -> Prometheus: up = {value}"

    def c_drift():
        call(f"{api}/simulate", {"mode": "drift", "duration_s": 240, "rps": 8})
        try:
            def fired():
                res = prom_query(prom, 'ALERTS{alertname="InputDriftPSI"}')
                return any(row["metric"].get("alertstate") == "firing" for row in res)
            firing = wait_until(fired, 150, every=5)
            psi = prom_query(prom, "model_input_drift_psi")
            value = float(psi[0]["value"][1]) if psi else float("nan")
            status = "firing" if firing else "belum firing"
            return bool(firing), f"PSI = {value:.2f}, alert InputDriftPSI {status}"
        finally:
            call(f"{api}/simulate", {"mode": "stop"})

    print(f"Cek stack: API {api} | Prometheus {prom} | Grafana {graf}\n")
    check("Model API sehat (/health)", c_health)
    check("Prediksi berjalan (/predict)", c_predict)
    check("Endpoint /metrics berisi metrik 3 layer", c_metrics)
    check("Prometheus siap", c_prom_ready)
    check("Semua target scrape up", c_targets)
    check("Blackbox probe website lokal sukses", c_probe)
    check("Alert rules 3 layer termuat", c_rules)
    check("PromQL membaca metrik model", c_promql)
    check("Grafana sehat", c_grafana)
    check("Dashboard ML Production ter-provision", c_dashboard)
    check("Grafana bisa query Prometheus", c_grafana_query)
    if args.drift:
        check("Simulasi drift memicu alert InputDriftPSI", c_drift)

    passed = sum(ok for ok, _ in results)
    print(f"\nHasil: {passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
