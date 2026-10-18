# Lab 10 — Monitoring, log terstruktur, SLI/SLO

<!-- lecture-materials:start -->

## Materi teori sebelum praktikum

- [Pertemuan 10: MLOps](slides/Teori_Pertemuan_10.pptx)

Slide menghubungkan konsep, kasus kerja, bacaan/video resmi, dan langkah lab.

<!-- lecture-materials:end -->

**Kebijakan kelas:** Lab ini latihan formatif, tanpa tugas, nilai, atau penyerahan terpisah. Satu proyek besar dikerjakan oleh kelompok **3 orang**, dengan presentasi checkpoint minggu 7 (UTS) dan hasil akhir minggu 14 (UAS). Simpan hasil lab hanya bila berguna sebagai referensi atau bukti proses proyek. Baca [brief proyek kelompok](PROYEK_KELOMPOK.md). Bobot resmi tetap mengikuti RPS/LMS.

**Capaian:** menjalankan synthetic uptime check untuk tiga service, menghitung availability dan p95, menetapkan SLO, membuat status page, dan membahas alert. Script memakai Python standard library; cloud account tidak diperlukan.

## Mulai praktikum lokal

Ikuti [modul mahasiswa langkah demi langkah](MODUL_MAHASISWA.md). Modul memakai **PowerShell, clone baru, satu perintah tiap langkah**, hasil yang diharapkan, dan screenshot contoh. Semua langkah utama berjalan lokal. Tidak ada laporan atau push terpisah yang wajib dikumpulkan.

## Log dan observability

Route Handler Lab 08 memakai `src/lib/logger.ts` dan mencatat JSON (`timestamp`, `level`, `event`, `requestId`, `status`, `durationMs`) pada log server Next.js. Buat beberapa catatan dan cocokkan request di terminal Next.js. Jangan log isi catatan, password, access token, atau webhook URL. Script ini mengukur **uptime** dan **latensi probe**; metrics, logs, dan traces adalah tiga sinyal berbeda. Core Web Vitals saat ini adalah LCP, INP, CLS; FID hanya metrik historis.

## Cloud opsional

- Salin `targets.cloud.example.json` menjadi `targets.cloud.json` dan sesuaikan dengan URL publik. File lokal itu diabaikan Git. Monitor ketiga sebaiknya endpoint health aplikasi yang mengecek dependensi Supabase secara aman, bukan URL database dengan credential di query string. Jalankan `python monitor.py --targets targets.cloud.json`.
- UptimeRobot atau layanan sejenis dapat memonitor URL publik jika akun tersedia; tiga monitor RPS dapat mewakili Vercel, HF Space, dan health BaaS melalui aplikasi. Jangan mengklaim status HF `DOWN` sebagai insiden aplikasi ketika Space sengaja tidur atau quota/plan tidak tersedia.
- Untuk Discord alert, set `DISCORD_WEBHOOK_URL` sebagai environment variable lokal/secret CI. Script mengirim setelah dua kegagalan berturut-turut. Jangan commit webhook URL.
- `status.html` dapat dipublikasikan pada host statis/GitHub Pages setelah URL internal dihapus dari konfigurasi yang akan diunggah. Halaman memuat nama service dan statistik, bukan credential.

**Bukti:** JSONL lima check, laporan p95/availability, satu simulasi DOWN, screenshot status page, dan contoh satu baris log JSON tanpa secret. **Git opsional:** push script dan target contoh saja.

Rujukan: [Google Core Web Vitals](https://web.dev/articles/vitals), [INP menggantikan FID](https://web.dev/blog/fid), [Vercel observability](https://vercel.com/docs/observability).

Checker mandiri: `python -B tests/challenge.py` menguji kode dengan server HTTP sementara tanpa tiga service lain; hasil **9 PASS, 0 FAIL**. Panduan: [modul mahasiswa dan kunci](MODUL_MAHASISWA.md), [panduan Git](PANDUAN_GIT.md). Screenshot berada di `screenshots/`.
