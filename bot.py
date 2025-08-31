import os
import logging
import json
import datetime
import calendar
from dotenv import load_dotenv

import google.generativeai as genai
from supabase import create_client, Client

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Muat environment variables dari file .env
load_dotenv()

# Konfigurasi logging untuk debugging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Inisialisasi Klien Eksternal ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Pastikan semua variabel lingkungan ada
if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Pastikan semua variabel lingkungan (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY) sudah diatur di file .env")

# Konfigurasi Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Inisialisasi Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Fungsi Handler Telegram ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengirim pesan sambutan ketika user memulai bot dengan /start."""
    user = update.effective_user
    welcome_message = (
        f"Halo, {user.first_name}! 👋\n\n"
        "Saya adalah bot pencatat keuangan pribadi Anda.\n\n"
        "Cukup kirimkan transaksi Anda dalam bahasa sehari-hari, contoh:\n"
        "➡️ `Makan siang di warteg 15000`\n"
        "➡️ `Dapat gaji bulanan 5000000`\n\n"
        "Saya akan otomatis mencatatnya untuk Anda."
    )
    await update.message.reply_html(welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani pesan teks dari user, menganalisisnya dengan Gemini, dan menyimpannya ke Supabase."""
    user_text = update.message.text
    user_id = update.effective_user.id

    # Kirim pesan bahwa bot sedang bekerja
    processing_message = await update.message.reply_text("🧠 Menganalisis transaksimu...")

    try:
        # Prompt untuk Gemini AI
        prompt = f"""
        Anda adalah API pemrosesan bahasa alami untuk bot pencatat keuangan.
        Tugas Anda adalah mengubah teks mentah dari pengguna menjadi format JSON yang terstruktur.

        Teks pengguna: "{user_text}"

        Format JSON yang harus Anda hasilkan harus memiliki kunci berikut:
        - "type": bisa "income" (pemasukan) atau "expense" (pengeluaran).
        - "amount": angka (integer atau float) dari jumlah transaksi.
        - "description": deskripsi singkat dari transaksi.

        ATURAN PENTING:
        1.  Prioritaskan "expense" jika ada kata kunci seperti: 'bayar', 'beli', 'biaya', 'untuk', 'kasih', 'keluar', 'jajan'.
        2.  Prioritaskan "income" jika ada kata kunci seperti: 'dapat', 'terima', 'gaji', 'bonus', 'dari', 'masuk'.
        3.  Untuk kasus ambigu seperti "uang bulanan", jika tidak ada kata kunci lain, anggap itu sebagai "expense".

        Jika teks tidak terlihat seperti transaksi keuangan, kembalikan JSON dengan "type": "none".

        Contoh Standar:
        - Teks: "Makan siang nasi padang 25000" -> {{"type": "expense", "amount": 25000, "description": "Makan siang nasi padang"}}
        - Teks: "dapat bonus akhir tahun 1.500.000" -> {{"type": "income", "amount": 1500000, "description": "Dapat bonus akhir tahun"}}

        Contoh Penanganan Ambiguitas:
        - Teks: "uang bulanan 1.600.000" -> {{"type": "expense", "amount": 1600000, "description": "Uang bulanan"}}
        - Teks: "bayar uang bulanan 1.600.000" -> {{"type": "expense", "amount": 1600000, "description": "Bayar uang bulanan"}}
        - Teks: "dapat uang bulanan dari ortu 500rb" -> {{"type": "income", "amount": 500000, "description": "Dapat uang bulanan dari ortu"}}
        - Teks: "halo apa kabar" -> {{"type": "none", "amount": 0, "description": "Bukan transaksi"}}

        Hanya kembalikan JSON, tanpa teks tambahan atau markdown.
        """

        # Panggil Gemini AI
        response = gemini_model.generate_content(prompt)

        # Bersihkan respons dari markdown
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '')

        # Parse JSON
        data = json.loads(cleaned_response_text)

        transaction_type = data.get("type")
        amount = data.get("amount")
        description = data.get("description")

        # Validasi data dari Gemini
        if transaction_type in ["income", "expense"] and isinstance(amount, (int, float)) and amount > 0:
            # Simpan ke Supabase
            payload = {
                "user_id": user_id,
                "type": transaction_type,
                "amount": amount,
                "description": description
            }
            db_response = supabase.table("transactions").insert(payload).execute()

            # Cek jika ada error saat menyimpan
            if db_response.data:
                # Kirim konfirmasi ke user
                confirmation_text = (
                    f"✅ Berhasil dicatat!\n\n"
                    f"Jenis: {'Pemasukan' if transaction_type == 'income' else 'Pengeluaran'}\n"
                    f"Jumlah: Rp{amount:,.0f}\n"
                    f"Deskripsi: {description}"
                )
                await processing_message.edit_text(confirmation_text)
            else:
                logger.error(f"Error saving to Supabase: {db_response.error}")
                await processing_message.edit_text("Maaf, terjadi kesalahan saat menyimpan data. Silakan coba lagi.")

        else:
            # Jika Gemini mengindikasikan ini bukan transaksi
            await processing_message.edit_text("Hmm, sepertinya itu bukan transaksi keuangan. Coba lagi dengan format seperti 'Makan siang 20000'.")

    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from Gemini response: {response.text}")
        await processing_message.edit_text("Maaf, saya kesulitan memahami respons dari AI. Coba sederhanakan kalimat Anda.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await processing_message.edit_text("Maaf, terjadi kesalahan yang tidak terduga. Tim kami sudah diberitahu.")


# --- Fungsi Handler Lanjutan ---

async def summary_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Memberikan ringkasan transaksi untuk tanggal tertentu. Format: /day DD-MM-YY"""
    user_id = update.effective_user.id

    try:
        date_str = context.args[0]
        day_obj = datetime.datetime.strptime(date_str, "%d-%m-%y").date()
    except (IndexError, ValueError):
        await update.message.reply_text("Format salah. Gunakan: /day DD-MM-YY (contoh: /day 31-08-25)")
        return

    start_of_day = datetime.datetime.combine(day_obj, datetime.time.min)
    end_of_day = start_of_day + datetime.timedelta(days=1)

    try:
        response = supabase.table("transactions").select("type, amount").eq("user_id", user_id).gte("created_at", start_of_day.isoformat()).lt("created_at", end_of_day.isoformat()).execute()

        total_income = 0
        total_expense = 0
        if response.data:
            for trx in response.data:
                if trx['type'] == 'income':
                    total_income += trx['amount']
                else:
                    total_expense += trx['amount']

        summary_message = (
            f"📊 **Ringkasan untuk {day_obj.strftime('%d %B %Y')}**\n\n"
            f"Pemasukan: Rp{total_income:,.0f}\n"
            f"Pengeluaran: Rp{total_expense:,.0f}"
        )
        await update.message.reply_html(summary_message)

    except Exception as e:
        logger.error(f"Error fetching daily summary: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mengambil ringkasan harian.")

async def summary_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Memberikan ringkasan transaksi untuk bulan tertentu. Format: /month MM-YY"""
    user_id = update.effective_user.id

    try:
        date_str = context.args[0]
        month_obj = datetime.datetime.strptime(date_str, "%m-%y")
    except (IndexError, ValueError):
        await update.message.reply_text("Format salah. Gunakan: /month MM-YY (contoh: /month 08-25)")
        return

    # Hitung tanggal awal bulan dan awal bulan berikutnya
    start_of_month = month_obj.replace(day=1)
    next_month = start_of_month.replace(day=28) + datetime.timedelta(days=4)  # Cara aman untuk ke bulan berikutnya
    end_of_month = next_month.replace(day=1)

    try:
        response = supabase.table("transactions").select("type, amount").eq("user_id", user_id).gte("created_at", start_of_month.isoformat()).lt("created_at", end_of_month.isoformat()).execute()

        total_income = 0
        total_expense = 0
        if response.data:
            for trx in response.data:
                if trx['type'] == 'income':
                    total_income += trx['amount']
                else:
                    total_expense += trx['amount']

        summary_message = (
            f"📊 **Ringkasan untuk {start_of_month.strftime('%B %Y')}**\n\n"
            f"Pemasukan: Rp{total_income:,.0f}\n"
            f"Pengeluaran: Rp{total_expense:,.0f}"
        )
        await update.message.reply_html(summary_message)

    except Exception as e:
        logger.error(f"Error fetching monthly summary: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mengambil ringkasan bulanan.")


# --- Fungsi Utama Bot ---

def main() -> None:
    """Mulai bot Telegram."""
    # Buat aplikasi bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Daftarkan handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("day", summary_day))
    application.add_handler(CommandHandler("month", summary_month))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Mulai bot (polling)
    logger.info("Bot dimulai...")
    application.run_polling()


if __name__ == '__main__':
    main()
