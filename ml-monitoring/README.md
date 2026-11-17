# Monitoring ML lokal: Prometheus + Grafana (Docker)

Praktik untuk materi **Pertemuan 10 ML in Production, Bagian 02 Monitoring**. Satu perintah menyalakan model API sentimen yang mengekspor metrik **3 layer** (sistem, model, bisnis), Prometheus yang mengambil metrik dan mengevaluasi alert, blackbox exporter yang mengecek website lokal dan web, serta Grafana dengan dashboard yang langsung tersedia. Semuanya gratis, jalan di laptop, tanpa akun cloud dan tanpa GPU.

| Container | Image | Port laptop | Fungsi |
|---|---|---|---|
| `model-api` | build lokal dari `python:3.12-slim` | 8090 | API sentimen, `/metrics`, panel simulasi |
| `prometheus` | `prom/prometheus:v3.13.5` (LTS) | 9090 | scrape metrik tiap 5 detik, evaluasi 7 alert |
| `blackbox` | `prom/blackbox-exporter:v0.29.1` | 9115 | cek URL lokal dan internet (synthetic check) |
| `grafana` | `grafana/grafana:13.3.1` | 3001 | dashboard *ML Production · Sentiment API* |

Unduhan pertama sekitar **700 MB** (Grafana sekitar 506 MB), jadi tarik image sebelum kelas. Saat berjalan, keempat container memakai sekitar **400 MB RAM**. Grafana sengaja di port 3001 agar port 3000 tetap bebas untuk Next.js Lab 08.

> Jangan ganti Grafana ke tag `-slim`. Varian itu tidak membawa plugin data source Prometheus, sehingga semua panel gagal dengan pesan *Plugin not registered* (sudah diuji).

## 1. Jalankan

Syarat: Docker menyala (`docker version` menampilkan bagian *Server*). Perintah di bawah sama untuk PowerShell (Windows) dan Terminal (macOS/Linux):

```
git clone https://github.com/SeedFlora/meet10CloudService.git
cd meet10CloudService/ml-monitoring
docker compose up -d --build
docker compose ps
```

Windows: dobel-klik `JALANKAN.bat` untuk menyalakan stack, menunggu container siap, dan menjalankan cek otomatis. Dobel-klik `MATIKAN.bat` untuk berhenti. Kedua launcher diuji di Windows lewat simulasi perintah Docker. Pengujian dengan Docker Desktop aktif masih diperlukan.

> **⚠ SESUAIKAN DI DEVICE-MU**
> - **Windows:** Docker Desktop dengan backend WSL2. **macOS:** Docker Desktop. **Linux:** Docker Engine + plugin `docker compose` (atau Docker Desktop).
> - **Port bentrok** (pesan *port is already allocated*): ubah port host (angka di tengah) pada `docker-compose.yml`, mis. `"127.0.0.1:3002:3000"` untuk Grafana, lalu buka port baru itu.
> - **RAM untuk Docker:** sisakan minimal 2 GB karena Grafana dan Prometheus berjalan bersamaan (macOS: Docker Desktop → Settings → Resources; Windows WSL2: batas memori diatur lewat `.wslconfig`).
> - **Jaringan kampus/kantor** yang memakai proxy: unduhan image dan probe ke huggingface.co bisa gagal; coba hotspot.

Keempat container harus berstatus `Up` (model-api `healthy`). Lalu buka:

| Alamat | Isi |
|---|---|
| http://localhost:8090 | Panel simulasi: coba prediksi, kirim trafik normal/drift, chaos |
| http://localhost:9090 | Prometheus: menu *Status → Target health*, *Alerts*, *Query* |
| http://localhost:3001 | Grafana: dashboard 3 layer langsung tampil tanpa login (login `admin`/`admin` hanya untuk mengedit) |

Cek otomatis tanpa memasang apa pun di laptop:

```powershell
docker compose exec model-api python check_stack.py
```

Hasil yang diharapkan: **11/11 PASS**. Tambahkan `--drift` untuk ikut menguji alert drift (sekitar 1 sampai 2 menit, hasil **12/12 PASS**).

## 2. Skenario demo (sekitar 15 menit)

Gunakan panel dan perintah pada tabel untuk mengikuti demo dari http://localhost:8090. Angka di bawah adalah hasil uji 16 November 2026.

| Langkah | Aksi | Yang terlihat di Grafana | Alert Prometheus |
|---|---|---|---|
| 1 | **Trafik normal** | sekitar 5 req/detik, p99 sekitar 2,5 ms, confidence sekitar 0,87, PSI sekitar 0,01, override di bawah 1% | tidak ada |
| 2 | **Trafik drift** (bahasa gaul dan campur Inggris) | p99 tetap di bawah 5 ms dan error 0%, tetapi confidence turun ke sekitar 0,43, PSI melonjak ke sekitar 8,8, override sekitar 54% | `InputDriftPSI`, `ConfidenceTurun`, `ManualOverrideTinggi` (firing sekitar 70 detik setelah klik) |
| 3 | **Trafik normal** lalu **Latensi +800 ms** dan **Error 20%** | p99 sekitar 1 detik, error rate naik ke kisaran 15 sampai 20%, request turun ke sekitar 1 per detik | `LatensiP99Tinggi`, `ErrorRateTinggi` |
| 4 | `docker compose stop model-api` | Model API dan website model-api `DOWN` | `ModelApiDown`, `WebsiteDown` |
| 5 | `docker compose start model-api`, **Reset normal**, **Trafik normal** | semua panel pulih | alert kembali *inactive* |

Pelajaran utamanya: pada langkah 2 layer sistem tetap hijau (latensi rendah, tidak ada error) padahal model memburuk. Monitoring yang hanya melihat CPU dan latensi tidak akan menangkap drift.

## 3. Pantau website hasil deploy (lokal dan web)

Blackbox exporter mengecek URL dari dalam Docker, seperti pengguna yang membuka website. Daftar URL ada di `prometheus/targets/web.yml` dan dibaca ulang otomatis tiap 30 detik, jadi tidak perlu restart.

```yaml
- targets: ["https://<user>-<space>.hf.space"]          # Hugging Face Space
  labels: {app: sentimen-space, lokasi: web}
- targets: ["https://<project>.vercel.app/api/ready"]   # Next.js Lab 08 di Vercel
  labels: {app: cloud-notes, lokasi: web}
```

Hasilnya muncul di *Status → Target health → web-probe* dan panel **Status website** di Grafana. Aplikasi lab sebelumnya yang jalan di laptop dijangkau lewat `host.docker.internal` (contoh ada di file, dalam komentar). Jalankan aplikasinya dengan host `0.0.0.0` agar bisa dijangkau dari container. Space yang sedang *sleeping* akan terbaca `DOWN`; itu status hosting, bukan bug aplikasi.

## 4. PromQL yang dipakai dashboard

| Layer | Pertanyaan | PromQL |
|---|---|---|
| Sistem | Request per detik | `sum(rate(http_requests_total{path="/predict"}[1m]))` |
| Sistem | p99 latensi | `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{path="/predict"}[1m])))` |
| Sistem | Error rate | `sum(rate(http_requests_total{path="/predict",status=~"5.."}[1m])) / sum(rate(http_requests_total{path="/predict"}[1m]))` |
| Model | Distribusi prediksi | `sum by (label) (rate(model_predictions_total[1m]))` |
| Model | Confidence rata-rata | `sum(rate(model_confidence_sum[1m])) / sum(rate(model_confidence_count[1m]))` |
| Model | Drift | `model_input_drift_psi` |
| Bisnis | Manual override | `sum(rate(model_feedback_total{verdict="salah"}[2m])) / sum(rate(model_feedback_total[2m]))` |
| Website | Status URL | `probe_success{job="web-probe"}` |

Drift dihitung dengan **PSI** (Population Stability Index) pada rasio kata yang tidak dikenal model (OOV) di 100 request terakhir, dibandingkan dengan data referensi. Patokan umum: di bawah 0,1 stabil, 0,1 sampai 0,2 waspada, di atas 0,2 drift. Kode ada di `model-api/model.py` (`psi`, `oov_bins`) dan `model-api/app.py`.

## 5. Struktur folder

```
ml-monitoring/
├─ docker-compose.yml
├─ model-api/            app.py (metrik + simulator), model.py (Naive Bayes + PSI), check_stack.py
├─ prometheus/           prometheus.yml, alerts.yml (7 alert), targets/web.yml
├─ blackbox/             blackbox.yml
└─ grafana/              provisioning (data source + dashboard), dashboards/ml-production.json
```

## 6. Masalah umum

| Gejala | Penyebab dan solusi |
|---|---|
| `port is already allocated` | Port 8090, 9090, 9115, atau 3001 dipakai aplikasi lain. Ubah port host di `ports`, misalnya `"127.0.0.1:3002:3000"`. |
| Panel Grafana *No data* | Belum ada trafik. Klik **Trafik normal**, tunggu 10 sampai 20 detik. |
| Website web `DOWN` | Cek internet atau proxy kampus. HF Space yang tidur perlu dibuka sekali di browser. |
| `docker compose` tidak dikenal | Perbarui Docker Desktop (Compose v2 sudah termasuk). |
| Ingin mengulang dari nol | `docker compose down -v` menghapus container beserta data metrik dan Grafana. |

Matikan setelah selesai dengan `docker compose down` (data metrik tetap tersimpan di volume).

## 7. Catatan untuk produksi

- `scrape_interval` 5 detik dan `for: 15s/30s` sengaja pendek untuk demo. Di produksi umumnya 15 sampai 30 detik dan 5 sampai 10 menit agar alert tidak berisik.
- Port stack hanya terbuka pada `127.0.0.1`. Login anonim dan password `admin` dipakai untuk lab lokal.
- Model API berjalan dengan satu worker. Bila memakai banyak worker, gunakan mode multiprocess `prometheus_client`.
- Alert di sini hanya tampil di Prometheus dan Grafana. Untuk notifikasi (email, Discord, Slack), tambahkan Alertmanager.

## 8. Bukti uji

Versi awal diuji pada 16 November 2026 di Linux dengan Docker 29.9.3 dan Compose v5.
Cek stack dengan `--drift` menghasilkan 12/12 PASS. Proxy jaringan workspace
dipakai untuk probe internet. Saat mengulang di lab, simpan keluaran
`docker compose ps` dan `check_stack.py --drift`, lalu bandingkan kondisi normal,
drift, dan pemulihan.

Uji ulang stack penuh dengan Docker Desktop Windows dan probe ke URL Space atau
Vercel milik kelompok masih diperlukan.
