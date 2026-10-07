# Lab 10 — Monitoring, log terstruktur, SLI/SLO

<!-- lecture-materials:start -->

## Materi teori sebelum praktikum

- [Pertemuan 10: MLOps](slides/Teori_Pertemuan_10.pptx)

Slide menghubungkan konsep, kasus kerja, bacaan/video resmi, dan langkah lab.

<!-- lecture-materials:end -->

**Kebijakan kelas:** Lab ini latihan formatif, tanpa tugas, nilai, atau penyerahan terpisah. Satu proyek besar dikerjakan oleh kelompok **3 orang**, dengan presentasi checkpoint minggu 7 (UTS) dan hasil akhir minggu 14 (UAS). Simpan hasil lab hanya bila berguna sebagai referensi atau bukti proses proyek. Baca [brief proyek kelompok](PROYEK_KELOMPOK.md). Bobot resmi tetap mengikuti RPS/LMS.

**Capaian:** menjalankan synthetic uptime check untuk tiga service, menghitung availability dan p95, menetapkan SLO, membuat status page, dan membahas alert. Script memakai Python standard library; cloud account tidak diperlukan.

## Jalankan lokal

Jalankan [API Lab 06](https://github.com/SeedFlora/meet6CloudService), [Next.js Lab 08](https://github.com/SeedFlora/meet8CloudService), dan [Gradio Lab 09](https://github.com/SeedFlora/meet9CloudService) pada komputer/Codespace yang sama. Dari root repo Lab 10:

```bash
python monitor.py --count 5 --interval 3 --reset
python report.py
python status.py
```

`--reset` memulai file observasi baru; untuk simulasi gangguan berikutnya jalankan monitor tanpa opsi ini agar histori bertambah. Buka `status.html` di browser. Hentikan salah satu service, ulangi monitor, lalu amati `DOWN`, availability, dan error budget. `observations.jsonl` diabaikan Git karena merekam data operasi lokal. Bila memakai `--output observations-baru.jsonl`, teruskan path yang sama ke `python report.py observations-baru.jsonl` dan `python status.py --input observations-baru.jsonl --output status-baru.html`.

`report.py` menghitung p95 hanya dari respons yang berhasil dan availability dari jumlah check yang berhasil. Ini **sampel kelas**, bukan SLO produksi yang valid dari lima permintaan. Contoh SLO 99% berarti maksimal 1% check boleh gagal dalam periode yang ditetapkan. Bahas mengapa satu kegagalan dari lima check langsung menghabiskan budget kecil tersebut.

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
