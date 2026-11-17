"""Model sentimen kecil (Multinomial Naive Bayes) + data referensi untuk deteksi drift.

Sengaja ditulis tanpa library ML agar image Docker ringan dan build cepat di laptop.
Fokus pertemuan ini adalah MONITORING model di produksi, bukan akurasi model.
"""

from __future__ import annotations

import math
import re
from collections import Counter

LABELS = ("positif", "negatif", "netral")
TOKEN_RE = re.compile(r"[a-z0-9]+")

# Data training: ulasan pendek bergaya aplikasi kampus / e-commerce.
TRAIN = [
    # positif
    ("aplikasinya cepat dan mudah dipakai", "positif"),
    ("pelayanan ramah dan responnya cepat", "positif"),
    ("pengiriman tepat waktu, barang rapi", "positif"),
    ("materi kuliah jelas dan bermanfaat", "positif"),
    ("saya puas dengan kualitas produknya", "positif"),
    ("fitur baru sangat membantu pekerjaan saya", "positif"),
    ("harga murah tapi kualitas bagus", "positif"),
    ("dosennya sabar dan penjelasannya mudah dipahami", "positif"),
    ("makanannya enak dan porsinya pas", "positif"),
    ("tampilan aplikasi rapi dan nyaman", "positif"),
    ("proses daftar sangat mudah", "positif"),
    ("admin cepat tanggap, masalah langsung selesai", "positif"),
    ("kualitas suara jernih, mantap", "positif"),
    ("aplikasi stabil, tidak pernah error", "positif"),
    ("terima kasih, pesanan sampai dengan aman", "positif"),
    ("praktikum hari ini seru dan jelas", "positif"),
    ("website kampus sekarang lebih cepat", "positif"),
    ("pembayaran lancar tanpa kendala", "positif"),
    ("rekomendasi produknya akurat dan bermanfaat", "positif"),
    ("baterai awet dan cepat diisi", "positif"),
    ("kurir ramah dan paket aman", "positif"),
    ("fitur pencarian akurat dan cepat", "positif"),
    ("sangat puas, pasti beli lagi", "positif"),
    ("modul praktikum lengkap dan mudah diikuti", "positif"),
    ("server stabil walaupun banyak pengguna", "positif"),
    ("chatbot menjawab dengan tepat dan sopan", "positif"),
    ("kopinya enak, tempatnya nyaman", "positif"),
    ("update terbaru membuat aplikasi makin ringan", "positif"),
    ("proses refund cepat dan jelas", "positif"),
    ("dashboard mudah dibaca dan informatif", "positif"),
    # negatif
    ("aplikasinya lambat dan sering error", "negatif"),
    ("pelayanan buruk, admin tidak membalas", "negatif"),
    ("pengiriman terlambat dan barang rusak", "negatif"),
    ("materi membingungkan dan terlalu cepat", "negatif"),
    ("saya kecewa dengan kualitas produknya", "negatif"),
    ("fitur baru malah menyulitkan", "negatif"),
    ("harga mahal tapi kualitas jelek", "negatif"),
    ("aplikasi sering crash saat dibuka", "negatif"),
    ("makanannya dingin dan hambar", "negatif"),
    ("tampilan berantakan dan susah dipakai", "negatif"),
    ("proses daftar ribet dan gagal terus", "negatif"),
    ("admin lama merespon, masalah tidak selesai", "negatif"),
    ("suara putus putus, sangat mengganggu", "negatif"),
    ("server down lagi saat ujian", "negatif"),
    ("pesanan hilang dan tidak ada kabar", "negatif"),
    ("login gagal terus, kesal sekali", "negatif"),
    ("website kampus lambat sekali", "negatif"),
    ("pembayaran gagal tapi saldo terpotong", "negatif"),
    ("rekomendasi tidak akurat dan tidak relevan", "negatif"),
    ("baterai cepat habis dan panas", "negatif"),
    ("kurir kasar dan paket penyok", "negatif"),
    ("pencarian tidak akurat dan lambat", "negatif"),
    ("kecewa, tidak akan beli lagi", "negatif"),
    ("modul praktikum tidak lengkap dan error", "negatif"),
    ("notifikasi spam dan mengganggu", "negatif"),
    ("chatbot menjawab ngawur dan tidak sopan", "negatif"),
    ("kopinya pahit, tempatnya kotor", "negatif"),
    ("update terbaru membuat aplikasi makin berat", "negatif"),
    ("refund lama dan tidak jelas", "negatif"),
    ("dashboard membingungkan dan lambat", "negatif"),
    # netral
    ("paket dikirim hari senin", "netral"),
    ("aplikasi ini dipakai untuk mencatat tugas", "netral"),
    ("harga produk lima puluh ribu rupiah", "netral"),
    ("kelas dimulai jam delapan pagi", "netral"),
    ("saya memesan dua buah kaos", "netral"),
    ("toko buka setiap hari kerja", "netral"),
    ("materi minggu depan tentang docker", "netral"),
    ("pesanan saya nomor dua belas", "netral"),
    ("aplikasi tersedia untuk android dan ios", "netral"),
    ("pembayaran bisa lewat transfer bank", "netral"),
    ("ukuran file sekitar dua megabyte", "netral"),
    ("praktikum dilaksanakan di laboratorium", "netral"),
    ("kurir datang sore hari", "netral"),
    ("server berada di jakarta", "netral"),
    ("saya mengganti alamat pengiriman", "netral"),
    ("jadwal ujian diumumkan minggu ini", "netral"),
    ("produk ini berwarna hitam", "netral"),
    ("tim kami terdiri dari empat orang", "netral"),
    ("data disimpan di database postgres", "netral"),
    ("dosen membagikan modul lewat lms", "netral"),
    ("pesanan akan diproses besok", "netral"),
    ("aplikasi meminta izin lokasi", "netral"),
    ("kopi dijual dalam ukuran besar dan kecil", "netral"),
    ("website menampilkan daftar mata kuliah", "netral"),
    ("saya bertanya tentang status pesanan", "netral"),
    ("laporan dikumpulkan dalam format pdf", "netral"),
    ("model dilatih dengan data ulasan", "netral"),
    ("chatbot ini menjawab pertanyaan akademik", "netral"),
    ("update tersedia di play store", "netral"),
    ("dashboard menampilkan jumlah pengunjung", "netral"),
]

# Data validasi: kalimat baru dengan kosakata yang mirip training.
# Dipakai sebagai distribusi REFERENSI untuk PSI dan sebagai trafik "normal".
HELDOUT = [
    ("pengiriman ke bandung cepat dan rapi", "positif"),
    ("aplikasi ojek ini mudah dipakai dan stabil", "positif"),
    ("pelayanan kasir ramah dan cepat", "positif"),
    ("materi cloud jelas dan bermanfaat", "positif"),
    ("kualitas kamera bagus, saya puas", "positif"),
    ("admin toko sepatu cepat tanggap", "positif"),
    ("kopi susu enak dan murah", "positif"),
    ("fitur jadwal sangat membantu", "positif"),
    ("aplikasi bank ini lancar dan aman", "positif"),
    ("chatbot kampus menjawab dengan tepat", "positif"),
    ("proses login sekarang cepat dan mudah", "positif"),
    ("grafik dashboard jelas dan informatif", "positif"),
    ("pengiriman ke bandung terlambat dan rusak", "negatif"),
    ("aplikasi ojek ini lambat dan sering crash", "negatif"),
    ("pelayanan kasir buruk dan lama", "negatif"),
    ("materi cloud membingungkan", "negatif"),
    ("kualitas kamera jelek, saya kecewa", "negatif"),
    ("admin toko sepatu tidak membalas", "negatif"),
    ("kopi susu hambar dan mahal", "negatif"),
    ("fitur jadwal sering error", "negatif"),
    ("aplikasi bank gagal terus saat login", "negatif"),
    ("chatbot kampus menjawab ngawur", "negatif"),
    ("website pendaftaran down lagi", "negatif"),
    ("grafik dashboard berantakan dan lambat", "negatif"),
    ("pengiriman ke bandung dijadwalkan besok", "netral"),
    ("aplikasi ojek tersedia untuk android", "netral"),
    ("kasir buka jam sembilan pagi", "netral"),
    ("materi cloud dibagikan lewat lms", "netral"),
    ("kamera produk ini berwarna hitam", "netral"),
    ("toko sepatu buka setiap hari", "netral"),
    ("kopi susu dijual dalam ukuran kecil", "netral"),
    ("jadwal praktikum diumumkan besok", "netral"),
    ("aplikasi bank meminta izin lokasi", "netral"),
    ("chatbot kampus menjawab pertanyaan jadwal", "netral"),
    ("website menampilkan daftar dosen", "netral"),
    ("grafik menampilkan jumlah pesanan", "netral"),
]

# Trafik "drift": bahasa gaul, singkatan, dan campur Inggris yang tidak ada di training.
DRIFT_POOL = [
    ("anjay mantul parah, auto langganan", "positif"),
    ("gokil sih ini, worth it banget", "positif"),
    ("literally the best app ever, love it", "positif"),
    ("kurirnya gercep, salut bestie", "positif"),
    ("cakep bgt ui nya, smooth", "positif"),
    ("top markotop, recommended pol", "positif"),
    ("smooth af, no lag at all", "positif"),
    ("keren abis, mimin fast respon", "positif"),
    ("ngebug mulu, uninstall aja deh", "negatif"),
    ("zonk parah, nyesel checkout", "negatif"),
    ("the app keeps crashing smh", "negatif"),
    ("kurirnya ghosting, paketnya ga nyampe nyampe", "negatif"),
    ("lemot bgt sumpah, bikin emosi", "negatif"),
    ("worst service ever, never again", "negatif"),
    ("php doang, katanya gratis ongkir", "negatif"),
    ("ui nya ribet bet, ga user friendly", "negatif"),
    ("btw ini bisa cod ga min", "netral"),
    ("otw checkout besok", "netral"),
    ("cmiiw, fiturnya baru rilis ya", "netral"),
    ("fyi promo berlaku sampai akhir bulan", "netral"),
    ("brp lama shipping ke medan", "netral"),
    ("ada versi dark mode ga ya", "netral"),
    ("pake akun google bisa ga", "netral"),
    ("min, ready stock?", "netral"),
]

NORMAL_POOL = TRAIN + HELDOUT

# Batas bin rasio OOV untuk PSI: [0,.05) [.05,.15) [.15,.3) [.3,.5) [.5,1]
OOV_EDGES = (0.05, 0.15, 0.3, 0.5)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class SentimentModel:
    """Multinomial Naive Bayes dengan Laplace smoothing."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.classes: tuple[str, ...] = LABELS
        self.word_count: dict[str, Counter] = {}
        self.total_words: dict[str, int] = {}
        self.log_prior: dict[str, float] = {}
        self.vocab: set[str] = set()

    @classmethod
    def train(cls, data=TRAIN) -> "SentimentModel":
        model = cls()
        labels = [label for _, label in data]
        model.word_count = {c: Counter() for c in model.classes}
        for text, label in data:
            model.word_count[label].update(tokenize(text))
        model.vocab = {w for c in model.classes for w in model.word_count[c]}
        model.total_words = {c: sum(model.word_count[c].values()) for c in model.classes}
        model.log_prior = {c: math.log(labels.count(c) / len(labels)) for c in model.classes}
        return model

    def predict_proba(self, text: str) -> dict[str, float]:
        tokens = [w for w in tokenize(text) if w in self.vocab]
        size = len(self.vocab)
        scores = {}
        for c in self.classes:
            denom = self.total_words[c] + self.alpha * size
            scores[c] = self.log_prior[c] + sum(
                math.log((self.word_count[c][w] + self.alpha) / denom) for w in tokens
            )
        top = max(scores.values())
        exp = {c: math.exp(s - top) for c, s in scores.items()}
        total = sum(exp.values())
        return {c: v / total for c, v in exp.items()}

    def oov_ratio(self, text: str) -> float:
        tokens = tokenize(text)
        if not tokens:
            return 1.0
        return sum(w not in self.vocab for w in tokens) / len(tokens)


def oov_bins(values) -> list[float]:
    """Proporsi per bin (dengan smoothing 0,5) agar PSI tidak membagi nol."""
    counts = [0] * (len(OOV_EDGES) + 1)
    for v in values:
        counts[sum(v >= e for e in OOV_EDGES)] += 1
    total = sum(counts) + 0.5 * len(counts)
    return [(c + 0.5) / total for c in counts]


def psi(expected: list[float], actual: list[float]) -> float:
    """Population Stability Index. < 0,1 stabil; 0,1-0,2 waspada; > 0,2 drift."""
    return sum((a - e) * math.log(a / e) for e, a in zip(expected, actual))
