# Bot Pencatat Keuangan Pribadi Cerdas

Bot Telegram cerdas untuk mencatat dan mengelola arus kas (pemasukan dan pengeluaran) harian Anda. Ditenagai oleh Google Gemini AI, bot ini memahami bahasa alami untuk interaksi yang lebih fleksibel dan intuitif.

## Fitur Utama

-   **Interaksi Berbasis AI**: Tidak perlu perintah kaku. Cukup bicara dengan bot seperti biasa, dan AI akan mengerti maksud Anda.
-   **Pencatatan Transaksi Cerdas**: Catat pemasukan dan pengeluaran dengan kalimat sehari-hari (misal: "beli kopi 25rb").
-   **Ringkasan Fleksibel**: Minta ringkasan dengan bahasa natural ("summary hari ini", "pengeluaran bulan lalu apa aja?").
-   **Manajemen Transaksi**: Edit atau hapus transaksi yang salah input dengan mudah melalui tombol inline.
-   **Kalkulasi Saldo Real-time**: Saldo Anda akan selalu diperbarui setelah setiap transaksi.
-   **Reset Data**: Mulai dari awal dengan fitur reset data yang aman (memerlukan konfirmasi).
-   **Multi-Pengguna**: Data setiap pengguna disimpan secara terpisah dan aman.

## Teknologi yang Digunakan

-   **Python**: Bahasa utama pengembangan bot.
-   **python-telegram-bot**: Library untuk berinteraksi dengan Telegram Bot API.
-   **Google Gemini AI**: Untuk pemrosesan bahasa alami (NLP), deteksi intent, dan ekstraksi data.
-   **Supabase**: Sebagai database PostgreSQL cloud untuk menyimpan semua data transaksi.

## Penyiapan dan Instalasi

Untuk menjalankan bot ini di lingkungan lokal Anda, ikuti langkah-langkah berikut:

**1. Clone Repositori**
```bash
git clone https://github.com/asdi-id/Bot-flow-cash.git
cd Bot-flow-cash
```

**2. Buat Virtual Environment (Direkomendasikan)**
```bash
python -m venv venv
source venv/bin/activate  # Di Windows, gunakan `venv\Scripts\activate`
```

**3. Install Dependensi**
```bash
pip install -r requirements.txt
```

**4. Siapkan Database Supabase**
-   Buat proyek baru di [Supabase](https://supabase.com).
-   Di dalam proyek Anda, navigasikan ke **SQL Editor**.
-   **Langkah A**: Salin seluruh konten dari file `database/schema.sql` dan jalankan untuk membuat tabel `transactions`.
-   **Langkah B**: Salin seluruh konten dari file `database/calculate_balance_rpc.sql` dan jalankan untuk membuat fungsi kalkulasi saldo yang efisien.

**5. Konfigurasi Environment Variables**
-   Salin file `.env.example` menjadi file baru bernama `.env`.
-   Isi semua variabel di dalam file `.env` dengan kredensial Anda.

**6. Jalankan Bot**
```bash
python bot.py
```
Bot Anda sekarang sudah aktif dan siap menerima pesan!

## Cara Penggunaan

-   **Mencatat Transaksi**:
    -   `bayar parkir 2000`
    -   `dapat gaji bulanan 5jt`

-   **Meminta Ringkasan**:
    -   `summary hari ini`
    -   `laporan bulan lalu`
    -   `cek pengeluaran kemarin`

-   **Mengelola Transaksi**:
    -   Setelah transaksi dicatat, akan muncul tombol **[✏️ Edit]** dan **[❌ Hapus]** di bawah pesan.
    -   Tekan tombol tersebut untuk mengelola transaksi yang bersangkutan.

-   **Mereset Data**:
    -   Kirim pesan: `reset semua dataku` atau `mulai dari awal lagi`.
    -   Bot akan meminta konfirmasi sebelum melakukan tindakan.