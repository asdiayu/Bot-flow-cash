import os
import logging
import json
import datetime
import calendar
import io
import matplotlib.pyplot as plt
from dotenv import load_dotenv

import google.generativeai as genai
from zhipuai import ZhipuAI
from supabase import create_client, Client

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
)

# Muat environment variables dari file .env
load_dotenv()

# Konfigurasi logging untuk debugging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Definisi State untuk ConversationHandler
AWAITING_EDIT_INPUT = 1


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
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

# Konfigurasi Zhipu AI
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
zhipu_client = ZhipuAI(api_key=ZHIPU_API_KEY) if ZHIPU_API_KEY else None

# Inisialisasi Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Fungsi Handler Telegram ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengirim pesan sambutan."""
    user = update.effective_user
    welcome_message = (
        f"Halo, {user.first_name}! 👋\n\n"
        "Saya adalah bot pencatat keuangan pribadi Anda.\n\n"
        "Cukup kirimkan transaksi atau pertanyaan Anda dalam bahasa sehari-hari.\n\n"
        "Contoh:\n"
        "- `beli kopi 25rb`\n"
        "- `gajian 5jt`\n"
        "- `summary hari ini`\n"
        "- `pengeluaran bulan lalu`\n"
        "- `saldo saya berapa?`"
    )
    await update.message.reply_text(welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fungsi utama yang menangani semua pesan teks dan bertindak sebagai router."""
    user_text = update.message.text

    # Kirim pesan bahwa bot sedang bekerja
    processing_message = await update.message.reply_text("🧠 Berpikir...")

    try:
        # Prompt untuk Zhipu AI (GLM)
        zhipu_router_prompt = f"""
        Analyze the user's text and classify it into one of the following intents: "log_transaction", "query_summary", "query_balance", "request_financial_report", "greeting", "request_reset", or "unknown".
        User Text: "{user_text}"
        Today's Date: {datetime.date.today().strftime('%Y-%m-%d')}
        Extract relevant information based on the intent. Respond ONLY with a valid JSON object.

        JSON Formats:
        1. log_transaction: {{"intent": "log_transaction", "transaction": {{"type": "income" | "expense", "amount": <float>, "description": "<string>", "category": "<string>"}}}}
           - Keywords for 'expense': 'beli', 'bayar', 'biaya'. Keywords for 'income': 'dapat', 'gaji', 'terima'.
           - Common categories: Makanan & Minuman, Transportasi, Tagihan, Belanja, Hiburan, Gaji, Bonus, Lainnya.

        2. query_summary: {{"intent": "query_summary", "query": {{"period": "today" | "yesterday" | "this_month" | "last_month", "type": "all" | "income" | "expense"}}}}

        3. query_balance: {{"intent": "query_balance"}}

        4. request_financial_report: {{"intent": "request_financial_report", "query": {{"period": "this_month" | "last_month"}}}}

        5. greeting: {{"intent": "greeting"}}

        6. request_reset: {{"intent": "request_reset"}}

        7. unknown: {{"intent": "unknown"}}

        Examples:
        - Text: "beli kopi 25000" -> {{"intent": "log_transaction", "transaction": {{"type": "expense", "amount": 25000, "description": "beli kopi", "category": "Makanan & Minuman"}}}}
        - Text: "summary hari ini" -> {{"intent": "query_summary", "query": {{"period": "today", "type": "all"}}}}
        - Text: "saldo saya berapa?" -> {{"intent": "query_balance"}}
        - Text: "beri aku analisis keuangan bulan ini" -> {{"intent": "request_financial_report", "query": {{"period": "this_month"}}}}
        """

        # Prompt untuk Gemini AI V2 - Router Intent
        gemini_router_prompt = f"""
        Anda adalah AI pusat untuk bot keuangan. Tugas Anda adalah menganalisis teks pengguna dan mengklasifikasikannya ke dalam salah satu "intent" berikut: "log_transaction", "query_summary", "query_balance", "request_financial_report", "greeting", "request_reset", atau "unknown".
        Kemudian, ekstrak informasi relevan berdasarkan intent tersebut.

        Teks Pengguna: "{user_text}"
        Tanggal Hari Ini: {datetime.date.today().strftime('%Y-%m-%d')}

        --- FORMAT JSON OUTPUT ---
        1.  Jika intentnya `log_transaction`, formatnya:
            {{"intent": "log_transaction", "transaction": {{"type": "income" | "expense", "amount": <float>, "description": "<string>", "category": "<string>"}}}}
            - Aturan: Gunakan kata kunci 'beli', 'bayar', 'biaya' untuk 'expense'. Gunakan 'dapat', 'gaji', 'terima' untuk 'income'.
            - Kategori umum: Makanan & Minuman, Transportasi, Tagihan, Belanja, Hiburan, Gaji, Bonus, Lainnya. Kategorikan sebaik mungkin.

        2.  Jika intentnya `query_summary`, formatnya:
            {{"intent": "query_summary", "query": {{"period": "<string>", "type": "all" | "income" | "expense"}}}}
            - `period` bisa berupa: "today", "yesterday", "this_month", "last_month".
            - `type` (opsional, default 'all'): jika pengguna menyebut "pemasukan" atau "pengeluaran".

        3.  Jika intentnya `query_balance` (cek total saldo), formatnya:
            {{"intent": "query_balance"}}

        4.  Jika intentnya `request_financial_report` (meminta analisis), ekstrak juga periodenya:
            {{"intent": "request_financial_report", "query": {{"period": "<string>"}}}}
            - `period` bisa berupa: "this_month", "last_month".

        5.  Jika intentnya `greeting` (sapaan), formatnya:
            {{"intent": "greeting"}}

        5.  Jika intentnya `request_reset` (meminta hapus semua data), formatnya:
            {{"intent": "request_reset"}}

        6.  Jika tidak cocok sama sekali, formatnya:
            {{"intent": "unknown"}}

        --- CONTOH ---
        - Teks: "beli kopi 25000" -> {{"intent": "log_transaction", "transaction": {{"type": "expense", "amount": 25000, "description": "beli kopi", "category": "Makanan & Minuman"}}}}
        - Teks: "dapat gaji 5jt" -> {{"intent": "log_transaction", "transaction": {{"type": "income", "amount": 5000000, "description": "dapat gaji", "category": "Gaji"}}}}
        - Teks: "bayar tagihan listrik 200rb" -> {{"intent": "log_transaction", "transaction": {{"type": "expense", "amount": 200000, "description": "bayar tagihan listrik", "category": "Tagihan"}}}}
        - Teks: "summary hari ini" -> {{"intent": "query_summary", "query": {{"period": "today", "type": "all"}}}}
        - Teks: "laporan bulan ini" -> {{"intent": "query_summary", "query": {{"period": "this_month", "type": "all"}}}}
        - Teks: "cek pengeluaran kemarin" -> {{"intent": "query_summary", "query": {{"period": "yesterday", "type": "expense"}}}}
        - Teks: "pemasukan bulan lalu apa aja?" -> {{"intent": "query_summary", "query": {{"period": "last_month", "type": "income"}}}}
        - Teks: "beri aku analisis keuangan bulan ini" -> {{"intent": "request_financial_report", "query": {{"period": "this_month"}}}}
        - Teks: "gimana keuanganku bulan lalu?" -> {{"intent": "request_financial_report", "query": {{"period": "last_month"}}}}
        - Teks: "saldo saya berapa?" -> {{"intent": "query_balance"}}
        - Teks: "uangku sisa berapa" -> {{"intent": "query_balance"}}
        - Teks: "hapus semua dataku" -> {{"intent": "request_reset"}}
        - Teks: "reset dong" -> {{"intent": "request_reset"}}
        - Teks: "halo bot" -> {{"intent": "greeting"}}
        - Teks: "cuaca hari ini gimana" -> {{"intent": "unknown"}}

        Hanya kembalikan JSON yang valid.
        """
        response_text = get_ai_response(gemini_prompt=gemini_router_prompt, zhipu_prompt=zhipu_router_prompt)
        if not response_text:
            await processing_message.edit_text("Maaf, layanan AI sedang tidak tersedia saat ini. Coba beberapa saat lagi.")
            return

        cleaned_response_text = response_text.strip().replace('```json', '').replace('```', '')
        data = json.loads(cleaned_response_text)

        intent = data.get("intent")

        # Hapus pesan "Berpikir..."
        await processing_message.delete()

        # Router berdasarkan intent
        if intent == "log_transaction":
            await process_new_transaction(update, context, data.get("transaction", {}))
        elif intent == "query_summary":
            await process_summary_query(update, context, data.get("query", {}))
        elif intent == "request_reset":
            await process_reset_request(update, context)
        elif intent == "request_financial_report":
            await process_financial_report(update, context, data.get("query", {}))
        elif intent == "query_balance":
            await process_balance_query(update, context)
        elif intent == "greeting":
            await process_greeting(update, context)
        else: # intent == "unknown" atau tidak ada intent
            await update.message.reply_text("Maaf, saya tidak mengerti maksud Anda. Coba katakan dengan cara lain.")

    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from Gemini response: {response.text}")
        await processing_message.edit_text("Maaf, saya kesulitan memahami respons dari AI. Coba sederhanakan kalimat Anda.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_message: {e}")
        await processing_message.edit_text("Maaf, terjadi kesalahan yang tidak terduga.")

    # Tidak ada return value karena ini adalah top-level handler
    return


# --- Fungsi Helper ---

def get_ai_response(gemini_prompt: str, zhipu_prompt: str) -> str:
    """
    Fungsi pusat untuk memanggil AI, dengan logika failover.
    Mencoba Gemini terlebih dahulu, jika gagal, beralih ke Zhipu AI.
    """
    # --- Coba AI Utama: Google Gemini ---
    try:
        logger.info("Attempting to call Gemini AI...")
        response = gemini_model.generate_content(gemini_prompt)
        if response and response.text:
            logger.info("Successfully received response from Gemini AI.")
            return response.text
        else:
            logger.warning("Gemini AI returned an empty response.")
    except Exception as e:
        logger.warning(f"Gemini AI failed: {e}. Trying Zhipu AI as failover.")

    # --- Coba AI Cadangan: Zhipu AI (GLM) ---
    if zhipu_client:
        try:
            logger.info("Attempting to call Zhipu AI (backup)...")
            response = zhipu_client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": zhipu_prompt}],
                temperature=0.1, # Rendah untuk output JSON yang konsisten
            )
            if response and response.choices[0].message.content:
                logger.info("Successfully received response from Zhipu AI.")
                return response.choices[0].message.content
            else:
                logger.warning("Zhipu AI returned an empty response.")
        except Exception as e:
            logger.error(f"Zhipu AI (backup) also failed: {e}")
    else:
        logger.warning("Zhipu AI client not configured. Cannot failover.")

    # Jika semua gagal
    logger.error("All AI providers failed.")
    return ""


def generate_pie_chart(chart_data: dict) -> io.BytesIO:
    """Membuat gambar grafik lingkaran dari data dan mengembalikannya sebagai buffer byte."""
    labels = chart_data.get('labels', [])
    values = chart_data.get('values', [])

    fig, ax = plt.subplots()
    ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig) # Tutup figure untuk membebaskan memori
    return buf


# --- Fungsi Logika Bisnis ---

async def process_new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_data: dict):
    """Menyimpan transaksi baru ke database dan mengirim konfirmasi."""
    user_id = update.effective_user.id

    transaction_type = transaction_data.get("type")
    amount = transaction_data.get("amount")
    description = transaction_data.get("description")
    category = transaction_data.get("category", "Lainnya") # Default ke 'Lainnya' jika AI tidak menemukan

    # Validasi data dari Gemini
    if transaction_type in ["income", "expense"] and isinstance(amount, (int, float)) and amount > 0 and description:
        try:
            # Simpan ke Supabase
            payload = { "user_id": user_id, "type": transaction_type, "amount": amount, "description": description, "category": category }
            db_response = supabase.table("transactions").insert(payload).execute()

            if db_response.data:
                # Panggil RPC untuk mendapatkan saldo terbaru
                rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
                current_balance = rpc_response.data if rpc_response.data is not None else 0

                # Buat Tombol Inline
                transaction_id = db_response.data[0]['id']
                keyboard = [[
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{transaction_id}"),
                    InlineKeyboardButton("❌ Hapus", callback_data=f"delete:{transaction_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Kirim konfirmasi ke user
                confirmation_text = (
                    f"✅ Berhasil dicatat!\n\n"
                    f"<b>Jenis:</b> {'Pemasukan' if transaction_type == 'income' else 'Pengeluaran'}\n"
                    f"<b>Jumlah:</b> Rp{amount:,.0f}\n"
                    f"<b>Deskripsi:</b> {description}\n"
                    f"<b>Kategori:</b> {category}\n\n"
                    f"💰 <b>Saldo Anda saat ini: Rp{current_balance:,.0f}</b>"
                )
                await update.message.reply_html(confirmation_text, reply_markup=reply_markup)
            else:
                logger.error(f"Error saving to Supabase: {db_response.error}")
                await update.message.reply_text("Maaf, terjadi kesalahan saat menyimpan data.")
        except Exception as e:
            logger.error(f"Error in process_new_transaction: {e}")
            await update.message.reply_text("Maaf, terjadi kesalahan internal saat memproses transaksi Anda.")
    else:
        # Jika data dari AI tidak lengkap/valid
        await update.message.reply_text("Maaf, saya tidak bisa mendapatkan detail yang lengkap dari pesan Anda. Mohon coba lagi.")

async def process_summary_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_data: dict):
    """Membuat query summary ke database dan mengirim hasilnya."""
    user_id = update.effective_user.id
    period = query_data.get("period", "today")
    query_type = query_data.get("type", "all")

    # Tentukan rentang tanggal berdasarkan periode
    today = datetime.date.today()
    start_date, end_date = None, None

    if period == "today":
        start_date = datetime.datetime.combine(today, datetime.time.min)
        end_date = start_date + datetime.timedelta(days=1)
        period_str = "hari ini"
    elif period == "yesterday":
        yesterday = today - datetime.timedelta(days=1)
        start_date = datetime.datetime.combine(yesterday, datetime.time.min)
        end_date = start_date + datetime.timedelta(days=1)
        period_str = "kemarin"
    elif period == "this_month":
        start_date = today.replace(day=1)
        next_month = start_date.replace(day=28) + datetime.timedelta(days=4)
        end_date = next_month.replace(day=1)
        period_str = f"bulan {start_date.strftime('%B %Y')}"
    elif period == "last_month":
        first_day_of_current_month = today.replace(day=1)
        end_date = first_day_of_current_month
        start_date = (end_date - datetime.timedelta(days=1)).replace(day=1)
        period_str = f"bulan {start_date.strftime('%B %Y')}"
    else:
        await update.message.reply_text("Maaf, saya tidak mengerti periode waktu yang Anda maksud.")
        return

    try:
        query = supabase.table("transactions").select("type, amount, description").eq("user_id", user_id).gte("created_at", start_date.isoformat()).lt("created_at", end_date.isoformat())

        if query_type != "all":
            query = query.eq("type", query_type)

        response = query.execute()

        total_income = 0
        total_expense = 0
        income_details = []
        expense_details = []

        if response.data:
            for trx in response.data:
                amount = trx['amount']
                description = trx['description']
                if trx['type'] == 'income':
                    total_income += amount
                    income_details.append(f"- Rp{amount:,.0f}: <i>{description}</i>")
                else:
                    total_expense += amount
                    expense_details.append(f"- Rp{amount:,.0f}: <i>{description}</i>")

        # Buat pesan summary
        title = f"📊 <b>Ringkasan untuk {period_str}</b>\n"
        summary_message = title

        if query_type in ["all", "income"] and income_details:
            summary_message += "\n<b>Rincian Pemasukan:</b>\n" + "\n".join(income_details) + "\n"

        if query_type in ["all", "expense"] and expense_details:
            summary_message += "\n<b>Rincian Pengeluaran:</b>\n" + "\n".join(expense_details) + "\n"

        summary_message += "\n<b>Total:</b>\n"
        summary_parts = []
        if query_type == "all" or query_type == "income":
            summary_parts.append(f"Pemasukan: Rp{total_income:,.0f}")
        if query_type == "all" or query_type == "expense":
            summary_parts.append(f"Pengeluaran: Rp{total_expense:,.0f}")
        summary_message += "\n".join(summary_parts)

        await update.message.reply_html(summary_message)

    except Exception as e:
        logger.error(f"Error fetching summary query: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mengambil ringkasan.")

async def process_greeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani sapaan dari pengguna."""
    await update.message.reply_text("Halo! Ada yang bisa saya bantu dengan pencatatan keuangan Anda?")

async def process_balance_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengambil dan mengirimkan total saldo pengguna saat ini."""
    user_id = update.effective_user.id
    try:
        rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
        current_balance = rpc_response.data if rpc_response.data is not None else 0
        await update.message.reply_html(f"💰 <b>Saldo Anda saat ini adalah: Rp{current_balance:,.0f}</b>")
    except Exception as e:
        logger.error(f"Error fetching balance query: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat mengambil saldo Anda.")

async def process_financial_report(update: Update, context: ContextTypes.DEFAULT_TYPE, query_data: dict):
    """Membuat laporan analisis keuangan lengkap dengan nasihat AI dan grafik."""
    user_id = update.effective_user.id
    period = query_data.get("period", "this_month")

    processing_message = await update.message.reply_text("🔍 Menganalisis data keuangan Anda, ini mungkin perlu beberapa saat...")

    # Tentukan rentang tanggal
    today = datetime.date.today()
    start_date, end_date = None, None
    if period == "this_month":
        start_date = today.replace(day=1)
        next_month = start_date.replace(day=28) + datetime.timedelta(days=4)
        end_date = next_month.replace(day=1)
        period_str = f"bulan {start_date.strftime('%B %Y')}"
    elif period == "last_month":
        first_day_of_current_month = today.replace(day=1)
        end_date = first_day_of_current_month
        start_date = (end_date - datetime.timedelta(days=1)).replace(day=1)
        period_str = f"bulan {start_date.strftime('%B %Y')}"
    else:
        await processing_message.edit_text("Maaf, periode untuk laporan analisis tidak valid.")
        return

    try:
        # 1. Ambil semua data transaksi mentah
        trx_response = supabase.table("transactions").select("description, amount, type, category").eq("user_id", user_id).gte("created_at", start_date.isoformat()).lt("created_at", end_date.isoformat()).execute()

        if not trx_response.data:
            await processing_message.edit_text(f"Tidak ada data transaksi ditemukan untuk {period_str}.")
            return

        # 2. Format data mentah untuk AI
        transactions_list_str = json.dumps(trx_response.data)

        # 3. Buat prompt analis data (lebih "lembut")
        zhipu_analyst_prompt = f"""
        You are a data assistant. Analyze the user's transaction list and provide insights.
        Transaction Data: {transactions_list_str}
        Tasks:
        1. Calculate total income, expense, and net savings.
        2. Identify top 3 expense categories.
        3. Provide a brief, neutral summary of the user's financial state.
        4. Provide 1-2 interesting "Observation Points". Do not give financial advice.
        5. Create data for a pie chart of expenses (top 4 categories + 'Others').
        Respond ONLY with a valid JSON object with keys "analysis_text", "actionable_tips", and "chart_data".
        """

        gemini_analyst_prompt = f"""
        Anda adalah seorang asisten data yang cerdas dan membantu.
        Tugas Anda adalah menganalisis daftar transaksi pengguna dan menyajikan data dalam format yang mudah dibaca.

        Berikut adalah data transaksi pengguna untuk {period_str} dalam format JSON:
        {transactions_list_str}

        Tugas Analisis:
        1.  Hitung Total Pemasukan, Total Pengeluaran, dan Uang Bersih (Pemasukan - Pengeluaran).
        2.  Identifikasi 3 kategori pengeluaran teratas.
        3.  Berikan ringkasan (1-2 kalimat) tentang kondisi keuangan pengguna bulan ini. Gunakan bahasa yang netral dan faktual.
        4.  Berikan 1 atau 2 "Poin Observasi" yang menarik dari data. Hindari memberi nasihat keuangan. Contoh: "Observasi: Pengeluaran terbesar Anda ada di kategori Makanan & Minuman." atau "Observasi: Pemasukan Anda lebih besar dari pengeluaran bulan ini.".
        5.  (Untuk Chart) Buat ringkasan data untuk pie chart pengeluaran. Kelompokkan 4 kategori teratas, dan sisanya gabungkan menjadi 'Lainnya'.

        Kembalikan hasil analisis Anda HANYA dalam format JSON yang valid seperti ini:
        {{
            "analysis_text": "<Ringkasan kondisi keuangan Anda di sini>",
            "actionable_tips": ["<Observasi pertama>", "<Observasi kedua>"],
            "chart_data": {{
                "labels": ["Makanan", "Transportasi", "Tagihan", "Hiburan", "Lainnya"],
                "values": [2000000, 1000000, 800000, 500000, 700000]
            }}
        }}
        """

        # 4. Panggil AI dengan failover
        response_text = get_ai_response(gemini_prompt=gemini_analyst_prompt, zhipu_prompt=zhipu_analyst_prompt)
        cleaned_response_text = response_text.strip().replace('```json', '').replace('```', '')

        # Tambahkan pengecekan respons kosong
        if not cleaned_response_text:
            await processing_message.edit_text("Maaf, AI tidak dapat menghasilkan analisis untuk data ini. Ini mungkin karena filter keamanan atau data yang terlalu kompleks.")
            return

        analysis_data = json.loads(cleaned_response_text)

        # 5. Tampilkan hasil dengan aman
        analysis_text = analysis_data.get('analysis_text', "AI tidak memberikan ringkasan teks saat ini.")
        actionable_tips = analysis_data.get('actionable_tips', [])
        chart_data = analysis_data.get('chart_data')

        report_text = f"📊 <b>Laporan Analisis Keuangan untuk {period_str}</b>\n\n"
        report_text += f"{analysis_text}\n"

        if actionable_tips:
            report_text += "\n<b>Observasi untuk Anda:</b>\n"
            for tip in actionable_tips:
                report_text += f"- <i>{tip}</i>\n"

        # Hapus pesan "menganalisis..."
        await processing_message.delete()

        # Kirim teks analisis
        await update.message.reply_html(report_text)

        # Buat dan kirim chart jika ada datanya
        if chart_data and chart_data.get('labels') and chart_data.get('values'):
            chart_buffer = generate_pie_chart(chart_data)
            await update.message.reply_photo(photo=chart_buffer)

    except Exception as e:
        logger.error(f"Error processing financial report: {e}")
        await processing_message.edit_text("Maaf, terjadi kesalahan saat membuat laporan analisis Anda.")

async def process_reset_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengirim pesan konfirmasi untuk mereset data."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Saya Yakin", callback_data="confirm_reset:yes"),
            InlineKeyboardButton("❌ Batal", callback_data="confirm_reset:no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    warning_text = (
        "⚠️ <b>Peringatan!</b> ⚠️\n"
        "Apakah Anda benar-benar yakin ingin menghapus SEMUA data transaksi Anda? "
        "Tindakan ini tidak dapat dibatalkan."
    )
    await update.message.reply_html(warning_text, reply_markup=reply_markup)


# --- Fungsi Handler Lanjutan ---

async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menangani input koreksi dari pengguna dengan konteks transaksi lama."""
    user_id = update.effective_user.id
    correction_text = update.message.text

    edit_transaction_id = context.user_data.get('edit_transaction_id')
    original_trx = context.user_data.get('original_trx')
    original_message_id = context.user_data.get('original_message_id')

    if not all([edit_transaction_id, original_trx, original_message_id]):
        await update.message.reply_text("Error: Sesi edit tidak valid atau telah berakhir. Silakan mulai lagi.")
        return ConversationHandler.END

    processing_message = await update.message.reply_text("🧠 Menerapkan koreksi Anda...")

    try:
        # Prompt untuk Zhipu AI (GLM)
        zhipu_edit_prompt = f"""
        You are a transaction editor. Given the original transaction and the user's correction, determine the new description and amount.
        Original Transaction: {{ "description": "{original_trx['description']}", "amount": {original_trx['amount']} }}
        User's Correction: "{correction_text}"
        Respond ONLY with a valid JSON object with "description" and "amount" keys.

        Examples:
        - Correction: "ganti jadi 20rb" -> {{"description": "{original_trx['description']}", "amount": 20000}}
        - Correction: "ternyata buat bayar parkir" -> {{"description": "bayar parkir", "amount": {original_trx['amount']}}}
        """

        # Prompt AI khusus untuk menginterpretasikan koreksi
        gemini_edit_prompt = f"""
        Anda adalah asisten editor transaksi keuangan. Tugas Anda adalah memodifikasi transaksi lama berdasarkan teks koreksi dari pengguna.

        Transaksi Asli:
        - Deskripsi: "{original_trx['description']}"
        - Jumlah: {original_trx['amount']}

        Teks Koreksi Pengguna: "{correction_text}"

        Tugas Anda:
        1. Analisis teks koreksi. Apakah pengguna ingin mengubah deskripsi, jumlah, atau keduanya?
        2. Jika pengguna hanya memberi nominal baru (misal: "salah, harusnya 15000" atau "15rb"), GANTI HANYA JUMLAHNYA dan pertahankan deskripsi asli.
        3. Jika pengguna hanya memberi deskripsi baru (misal: "deskripsinya jadi beli makan malam"), GANTI HANYA DESKRIPSINYA dan pertahankan jumlah asli.
        4. Jika pengguna memberikan kalimat transaksi lengkap baru, gunakan itu.
        5. Kembalikan hasilnya dalam format JSON dengan kunci "description" dan "amount".

        Contoh:
        - Koreksi: "ganti jadi 20rb" -> {{"description": "{original_trx['description']}", "amount": 20000}}
        - Koreksi: "ternyata buat bayar parkir" -> {{"description": "bayar parkir", "amount": {original_trx['amount']}}}
        - Koreksi: "oh salah, harusnya makan malam 75000" -> {{"description": "makan malam", "amount": 75000}}

        Hanya kembalikan JSON yang valid.
        """
        response_text = get_ai_response(gemini_prompt=gemini_edit_prompt, zhipu_prompt=zhipu_edit_prompt)
        if not response_text:
            await processing_message.edit_text("Maaf, layanan AI sedang tidak tersedia saat ini. Coba beberapa saat lagi.")
            # Bersihkan state dan akhiri conversation
            context.user_data.pop('edit_transaction_id', None)
            context.user_data.pop('original_trx', None)
            context.user_data.pop('original_message_id', None)
            return ConversationHandler.END

        cleaned_response_text = response_text.strip().replace('```json', '').replace('```', '')
        data = json.loads(cleaned_response_text)

        new_amount = data.get("amount")
        new_description = data.get("description")

        if isinstance(new_amount, (int, float)) and new_description:
            # Dapatkan tipe dan kategori transaksi lama
            original_data_response = supabase.table("transactions").select("type, category").eq("id", edit_transaction_id).single().execute()
            transaction_type = original_data_response.data['type']
            category = original_data_response.data.get('category', 'Lainnya') # Gunakan kategori lama

            payload = {"amount": new_amount, "description": new_description, "category": category}
            db_response = supabase.table("transactions").update(payload).eq("id", edit_transaction_id).eq("user_id", user_id).execute()

            await processing_message.delete()

            rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
            current_balance = rpc_response.data if rpc_response.data is not None else 0

            keyboard = [[
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{edit_transaction_id}"),
                InlineKeyboardButton("❌ Hapus", callback_data=f"delete:{edit_transaction_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            confirmation_text = (
                f"✅ <b>Transaksi Diperbarui!</b>\n\n"
                f"<b>Jenis:</b> {'Pemasukan' if transaction_type == 'income' else 'Pengeluaran'}\n"
                f"<b>Jumlah:</b> Rp{new_amount:,.0f}\n"
                f"<b>Deskripsi:</b> {new_description}\n"
                f"<b>Kategori:</b> {category}\n\n"
                f"💰 <b>Saldo Anda saat ini: Rp{current_balance:,.0f}</b>"
            )
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, message_id=original_message_id,
                text=confirmation_text, parse_mode='HTML', reply_markup=reply_markup
            )
        else:
            await processing_message.edit_text("Maaf, saya tidak bisa memahami koreksi Anda. Coba lagi atau batalkan dengan /cancel.")
            return AWAITING_EDIT_INPUT # Tetap di mode edit

    except Exception as e:
        logger.error(f"Error processing smart edit input: {e}")
        await processing_message.edit_text("Maaf, terjadi kesalahan saat memproses editan Anda.")

    # Bersihkan state dan akhiri conversation
    context.user_data.pop('edit_transaction_id', None)
    context.user_data.pop('original_trx', None)
    context.user_data.pop('original_message_id', None)
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menangani semua aksi dari tombol inline dengan urutan logika yang benar."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    parts = query.data.split(":", 1)
    action = parts[0]
    value = parts[1] if len(parts) > 1 else None

    if not value:
        await query.edit_message_text(text="Error: Aksi dari tombol tidak valid.")
        return

    # Konversi value ke integer jika diperlukan oleh aksi
    transaction_id = None
    if action in ["edit", "delete", "confirm_delete", "cancel_delete"]:
        try:
            transaction_id = int(value)
        except (ValueError, TypeError):
            await query.edit_message_text(text="Error: ID transaksi pada tombol tidak valid.")
            return

    # --- Rute Aksi ---
    if action == "delete":
        keyboard = [
            [
                InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"confirm_delete:{transaction_id}"),
                InlineKeyboardButton("❌ Batal", callback_data=f"cancel_delete:{transaction_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Apakah Anda yakin ingin menghapus transaksi ini?", reply_markup=reply_markup)

    elif action == "confirm_delete":
        try:
            delete_response = supabase.table("transactions").delete().match({'id': transaction_id, 'user_id': user_id}).execute()
            if delete_response.data:
                rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
                current_balance = rpc_response.data if rpc_response.data is not None else 0
                await query.edit_message_text(
                    text=f"✅ Transaksi telah dihapus.\n\n💰 <b>Saldo Anda sekarang: Rp{current_balance:,.0f}</b>",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(text="Gagal menghapus: Transaksi tidak ditemukan atau Anda tidak punya hak akses.")
        except Exception as e:
            logger.error(f"Error during confirm_delete: {e}")
            await query.edit_message_text(text="Maaf, terjadi kesalahan saat mencoba menghapus transaksi.")

    elif action == "cancel_delete":
        try:
            trx_response = supabase.table("transactions").select("type, amount, description, category").eq("id", transaction_id).eq("user_id", user_id).single().execute()
            if trx_response.data:
                trx = trx_response.data
                rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
                current_balance = rpc_response.data if rpc_response.data is not None else 0
                keyboard = [[
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{transaction_id}"),
                    InlineKeyboardButton("❌ Hapus", callback_data=f"delete:{transaction_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                confirmation_text = (
                    f"✅ Berhasil dicatat!\n\n"
                    f"<b>Jenis:</b> {'Pemasukan' if trx['type'] == 'income' else 'Pengeluaran'}\n"
                    f"<b>Jumlah:</b> Rp{trx['amount']:,.0f}\n"
                    f"<b>Deskripsi:</b> {trx['description']}\n"
                    f"<b>Kategori:</b> {trx.get('category', 'Lainnya')}\n\n"
                    f"💰 <b>Saldo Anda saat ini: Rp{current_balance:,.0f}</b>"
                )
                await query.edit_message_text(text=confirmation_text, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await query.edit_message_text(text="Gagal membatalkan: Transaksi asli tidak ditemukan lagi.")
        except Exception as e:
            logger.error(f"Error during cancel_delete: {e}")
            await query.edit_message_text(text="Maaf, terjadi kesalahan saat mencoba membatalkan.")

    elif action == "edit":
        try:
            original_trx_response = supabase.table("transactions").select("description, amount").eq("id", transaction_id).eq("user_id", user_id).single().execute()
            if not original_trx_response.data:
                await query.edit_message_text("Error: Transaksi asli tidak ditemukan.")
                return
            context.user_data['edit_transaction_id'] = transaction_id
            context.user_data['original_message_id'] = query.message.message_id
            context.user_data['original_trx'] = original_trx_response.data
            keyboard = [[InlineKeyboardButton("❌ Batal", callback_data="cancel_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "<b>Mode Edit Aktif.</b>\n"
                "Kirimkan koreksi Anda (misal: 'salah, harusnya 15rb' atau 'deskripsinya jadi beli makan malam').",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return AWAITING_EDIT_INPUT
        except Exception as e:
            logger.error(f"Error fetching transaction for edit: {e}")
            await query.edit_message_text("Maaf, terjadi kesalahan saat mencoba mengedit.")
            return

    elif action == "cancel_edit":
        # Hapus pesan "Mode Edit Aktif..."
        await query.message.delete()
        # Hapus state dari user_data
        context.user_data.pop('edit_transaction_id', None)
        context.user_data.pop('original_trx', None)
        context.user_data.pop('original_message_id', None)
        # Tidak perlu return state karena ini bukan bagian dari ConversationHandler
        return

    elif action == "confirm_reset":
        if value == "yes":
            try:
                delete_response = supabase.table("transactions").delete().eq("user_id", user_id).execute()
                await query.edit_message_text(text="✅ Semua data transaksi Anda telah berhasil dihapus.")
            except Exception as e:
                logger.error(f"Error resetting data: {e}")
                await query.edit_message_text(text="Maaf, terjadi kesalahan teknis saat mereset data.")
        else:  # value == "no"
            await query.edit_message_text(text="Aksi dibatalkan. Data Anda aman.")



# --- Fungsi Utama Bot ---

def main() -> None:
    """Mulai bot Telegram."""
    # Buat aplikasi bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ConversationHandler untuk alur Edit
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^edit:.*")],
        states={
            AWAITING_EDIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_input)
            ],
        },
        fallbacks=[],
        per_user=True,
        # Izinkan pengguna untuk memulai ulang conversation kapan saja
        allow_reentry=True
    )

    # Daftarkan handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler) # Handler untuk alur edit
    # Handler untuk semua tombol di luar percakapan edit
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(delete|confirm_delete|cancel_delete|confirm_reset|cancel_edit).*"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)) # Handler utama untuk teks

    # Mulai bot (polling)
    logger.info("Bot dimulai...")
    application.run_polling()


if __name__ == '__main__':
    main()
