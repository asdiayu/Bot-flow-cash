# Bot Pencatat Keuangan Pribadi

Bot Telegram cerdas untuk mencatat arus kas (pemasukan dan pengeluaran) harian Anda menggunakan pemrosesan bahasa alami yang didukung oleh Google Gemini AI dan database Supabase.

## Fitur Utama

-   **Pencatatan Bahasa Alami**: Cukup kirim pesan seperti "Beli kopi susu 25 ribu" atau "Gajian 5 juta" dan biarkan AI yang memprosesnya.
-   **Ringkasan Harian**: Dapatkan rekapitulasi pemasukan dan pengeluaran untuk tanggal tertentu dengan perintah `/day DD-MM-YY`.
-   **Ringkasan Bulanan**: Dapatkan rekapitulasi untuk bulan tertentu dengan perintah `/month MM-YY`.
-   **Multi-Pengguna**: Data setiap pengguna disimpan secara terpisah dan aman berdasarkan ID unik Telegram.

## Teknologi yang Digunakan

-   **Python**: Bahasa utama pengembangan bot.
-   **python-telegram-bot**: Library untuk berinteraksi dengan Telegram Bot API.
-   **Google Gemini AI**: Untuk pemrosesan bahasa alami (NLP) dan ekstraksi data dari teks.
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
Pastikan semua library yang dibutuhkan terinstal.
```bash
pip install -r requirements.txt
```

**4. Siapkan Database Supabase**
-   Buat proyek baru di [Supabase](https://supabase.com).
-   Di dalam proyek Anda, navigasikan ke **SQL Editor**.
-   Salin seluruh konten dari file `database/schema.sql` dan jalankan di editor untuk membuat tabel `transactions`.

**5. Konfigurasi Environment Variables**
-   Salin file `.env.example` menjadi file baru bernama `.env`.
-   Isi semua variabel di dalam file `.env` dengan kredensial Anda:
    -   `TELEGRAM_BOT_TOKEN`: Token bot dari BotFather di Telegram.
    -   `GEMINI_API_KEY`: Kunci API Anda dari Google AI Studio.
    -   `SUPABASE_URL`: URL proyek Supabase Anda (ada di Project Settings > API).
    -   `SUPABASE_KEY`: Kunci `anon` `public` proyek Supabase Anda (ada di Project Settings > API).

**6. Jalankan Bot**
```bash
python bot.py
```
Bot Anda sekarang sudah aktif dan siap menerima pesan!

## Cara Penggunaan

-   **Mencatat Transaksi**:
    -   Kirim pesan: `Makan siang 20000`
    -   Kirim pesan: `Dapat bonus 500rb`

-   **Melihat Ringkasan Harian**:
    -   Kirim perintah: `/day 31-08-25`

-   **Melihat Ringkasan Bulanan**:
    -   Kirim perintah: `/month 08-25`