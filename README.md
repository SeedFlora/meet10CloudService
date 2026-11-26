# Lab 10 — Monitoring, log terstruktur, SLI/SLO

## Mulai dari kelasmu

| Saya ingin… | Buka panduan ini |
|---|---|
| Mengikuti **Teori 10 LA75** dari nol | [Jalankan simulator, Prometheus, dan Grafana di Docker lokal atau GitHub Codespaces](ml-monitoring/README.md). Di Codespaces pilih branch `main`. Setelah checker menampilkan **11/11 PASS**, buka tab **Ports**. |
| Mengubah **tampilan Grafana atau web simulator** | [Panduan modifikasi Teori 10](ml-monitoring/README.md#modifikasi-tampilan). Ada contoh mengubah warna dan judul grafik, menambah panel prediksi lima menit, serta mengganti tampilan simulator. |
| Mengerjakan **Lab 10** tentang uptime, log, dan SLO | [Modul Lab 10](MODUL_MAHASISWA.md). Gunakan skrip Python dari folder utama repo ini untuk mengambil sampel HTTP dan membuat laporan. |
| Mengubah **web Cloud Notes di Lab 08 BA75/BB75** | [Panduan edit web di repo Lab 08](https://github.com/SeedFlora/meet8CloudService/tree/lab08-docker-codespaces#modifikasi-halaman-cloud-notes). Di sana kamu bisa mengubah teks, tombol, warna, dan judul tab, lalu menguji kembali penyimpanan catatan. |

<!-- lecture-materials:start -->

## Materi teori sebelum praktikum

- [Pertemuan 10: MLOps](slides/Teori_Pertemuan_10.pptx)

Slide menghubungkan konsep, kasus kerja, bacaan/video resmi, dan langkah lab.

<!-- lecture-materials:end -->

**Kebijakan kelas:** Lab ini latihan formatif, tanpa tugas, nilai, atau penyerahan terpisah. Satu proyek besar dikerjakan oleh kelompok **3 orang**, dengan presentasi checkpoint minggu 7 (UTS) dan hasil akhir minggu 14 (UAS). Simpan hasil lab hanya bila berguna sebagai referensi atau bukti proses proyek. Baca [brief proyek kelompok](PROYEK_KELOMPOK.md). Bobot resmi tetap mengikuti RPS/LMS.

**Capaian:** menjalankan synthetic uptime check untuk tiga service, menghitung availability dan p95, menetapkan SLO, membuat status page, dan membahas alert. Script memakai Python standard library; cloud account tidak diperlukan.

## Mulai praktikum lokal

Ikuti [modul mahasiswa langkah demi langkah](MODUL_MAHASISWA.md). Modul memakai **PowerShell, clone baru, satu perintah tiap langkah**, hasil yang diharapkan, dan screenshot contoh. Semua langkah utama berjalan lokal. Tidak ada laporan atau push terpisah yang wajib dikumpulkan.

## Demo Teori 10 dengan Prometheus dan Grafana

Jalankan perintah dari folder `ml-monitoring`. Jika terminal masih di folder utama repo, masuk dengan `cd ml-monitoring`. Lalu jalankan satu baris setiap kali.

```sh
docker compose up -d --build --wait
docker compose exec -T model-api python check_stack.py
```

Di laptop, buka [simulator](http://127.0.0.1:8090), [dashboard Grafana](http://127.0.0.1:3001/d/ml-production?from=now-5m&to=now&refresh=5s), dan [target Prometheus](http://127.0.0.1:9090/targets). Di Codespaces, buka port privat **8090**, **3001**, dan **9090** melalui **Ports → Open in Browser**. Di simulator klik **Trafik normal**, tunggu kira-kira satu menit, lalu catat confidence dan PSI sebelum beralih ke **Trafik drift (bahasa gaul)**. Untuk memahami apa yang berubah dan mengedit tampilannya, ikuti [README monitoring](ml-monitoring/README.md).

## Log dan observability

Route Handler Lab 08 memakai `src/lib/logger.ts` dan mencatat JSON (`timestamp`, `level`, `event`, `requestId`, `status`, `durationMs`) pada log server Next.js. Buat beberapa catatan dan cocokkan request di terminal Next.js. Jangan log isi catatan, password, access token, atau webhook URL. Script ini mengukur **uptime** dan **latensi probe**; metrics, logs, dan traces adalah tiga sinyal berbeda. Core Web Vitals saat ini adalah LCP, INP, CLS; FID hanya metrik historis.

## Cloud opsional

- Salin `targets.cloud.example.json` menjadi `targets.cloud.json` dan sesuaikan dengan URL publik. File lokal itu diabaikan Git. Monitor ketiga sebaiknya endpoint health aplikasi yang mengecek dependensi Supabase secara aman, bukan URL database dengan credential di query string. Jalankan `python monitor.py --targets targets.cloud.json`.
- UptimeRobot atau layanan sejenis dapat memonitor URL publik jika akun tersedia; tiga monitor RPS dapat mewakili Vercel, HF Space, dan health BaaS melalui aplikasi. Jangan mengklaim status HF `DOWN` sebagai insiden aplikasi ketika Space sengaja tidur atau quota/plan tidak tersedia.
- Untuk Discord alert, set `DISCORD_WEBHOOK_URL` sebagai environment variable lokal/secret CI. Script mengirim setelah dua kegagalan berturut-turut. Jangan commit webhook URL.
- `status.html` dapat dipublikasikan pada host statis/GitHub Pages setelah URL internal dihapus dari konfigurasi yang akan diunggah. Halaman memuat nama service dan statistik, bukan credential.

**Bukti:** JSONL lima check, laporan p95/availability, satu simulasi DOWN, screenshot status page, dan contoh satu baris log JSON tanpa secret. **Git opsional:** push script dan target contoh saja.

Rujukan: [Google Core Web Vitals](https://web.dev/articles/vitals), [INP menggantikan FID](https://web.dev/blog/fid), [Vercel observability](https://vercel.com/docs/observability).

**Tambahan: monitor endpoint AI.** `targets.ai.example.json` memantau `/gradio_api/info` (metadata API Lab 09), `/ready` (koneksi database RAG Lab 11), `/api/ready` (API Lab 06 dari Next.js Lab 08), dan `/v1/models` (daftar model Ollama). Kirim inferensi terpisah untuk menguji apakah model dapat menjawab. Jalankan `python monitor.py --targets targets.ai.example.json --output ai_observations.jsonl --reset --count 3 --interval 0`, `python report.py ai_observations.jsonl`, lalu `python status.py --input ai_observations.jsonl --output ai_status.html` (macOS/Linux: `python3`). Jalankan probe sebelum dan setelah menghentikan Ollama untuk membandingkan status Ollama dengan readiness Next.js. Untuk API model dari penyedia cloud, catat juga rasio HTTP 429/5xx dan sisa kuota harian dari dashboard provider.

> **⚠ SESUAIKAN DI DEVICE-MU:** Windows memakai `python` (atau `py`), macOS/Linux memakai `python3`; tidak ada paket tambahan. Hapus baris target untuk layanan yang tidak kamu jalankan (target yang mati akan DOWN) dan ubah port bila Lab 08/09/11 atau Ollama berjalan di port lain. `ai_status.html` cukup dibuka dengan dobel-klik.

Checker mandiri: `python -B tests/challenge.py` menguji kode dengan server HTTP sementara tanpa tiga service lain; hasil **9 PASS, 0 FAIL**. Panduan: [modul mahasiswa dan kunci](MODUL_MAHASISWA.md), [panduan Git](PANDUAN_GIT.md). Screenshot berada di `screenshots/`.
