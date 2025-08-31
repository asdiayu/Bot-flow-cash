import os
import logging
import json
import datetime
import calendar
from dotenv import load_dotenv

import google.generativeai as genai
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
ROUTING, AWAITING_EDIT_INPUT = range(2)


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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Memulai percakapan dan mengirim pesan sambutan."""
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
    return ROUTING


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fungsi utama yang menangani semua pesan teks dan bertindak sebagai router."""
    user_text = update.message.text

    # Kirim pesan bahwa bot sedang bekerja
    processing_message = await update.message.reply_text("🧠 Berpikir...")

    try:
        # Prompt untuk Gemini AI V2 - Router Intent
        prompt = f"""
        Anda adalah AI pusat untuk bot keuangan. Tugas Anda adalah menganalisis teks pengguna dan mengklasifikasikannya ke dalam salah satu "intent" berikut: "log_transaction", "query_summary", "query_balance", "greeting", "request_reset", atau "unknown".
        Kemudian, ekstrak informasi relevan berdasarkan intent tersebut.

        Teks Pengguna: "{user_text}"
        Tanggal Hari Ini: {datetime.date.today().strftime('%Y-%m-%d')}

        --- FORMAT JSON OUTPUT ---
        1.  Jika intentnya `log_transaction`, formatnya:
            {{"intent": "log_transaction", "transaction": {{"type": "income" | "expense", "amount": <float>, "description": "<string>"}}}}
            - Aturan: Gunakan kata kunci 'beli', 'bayar', 'biaya' untuk 'expense'. Gunakan 'dapat', 'gaji', 'terima' untuk 'income'.

        2.  Jika intentnya `query_summary`, formatnya:
            {{"intent": "query_summary", "query": {{"period": "<string>", "type": "all" | "income" | "expense"}}}}
            - `period` bisa berupa: "today", "yesterday", "this_month", "last_month".
            - `type` (opsional, default 'all'): jika pengguna menyebut "pemasukan" atau "pengeluaran".

        3.  Jika intentnya `query_balance` (cek total saldo), formatnya:
            {{"intent": "query_balance"}}

        4.  Jika intentnya `greeting` (sapaan), formatnya:
            {{"intent": "greeting"}}

        5.  Jika intentnya `request_reset` (meminta hapus semua data), formatnya:
            {{"intent": "request_reset"}}

        6.  Jika tidak cocok sama sekali, formatnya:
            {{"intent": "unknown"}}

        --- CONTOH ---
        - Teks: "beli kopi 25000" -> {{"intent": "log_transaction", "transaction": {{"type": "expense", "amount": 25000, "description": "beli kopi"}}}}
        - Teks: "dapat gaji 5jt" -> {{"intent": "log_transaction", "transaction": {{"type": "income", "amount": 5000000, "description": "dapat gaji"}}}}
        - Teks: "summary hari ini" -> {{"intent": "query_summary", "query": {{"period": "today", "type": "all"}}}}
        - Teks: "laporan bulan ini" -> {{"intent": "query_summary", "query": {{"period": "this_month", "type": "all"}}}}
        - Teks: "cek pengeluaran kemarin" -> {{"intent": "query_summary", "query": {{"period": "yesterday", "type": "expense"}}}}
        - Teks: "pemasukan bulan lalu apa aja?" -> {{"intent": "query_summary", "query": {{"period": "last_month", "type": "income"}}}}
        - Teks: "saldo saya berapa?" -> {{"intent": "query_balance"}}
        - Teks: "uangku sisa berapa" -> {{"intent": "query_balance"}}
        - Teks: "hapus semua dataku" -> {{"intent": "request_reset"}}
        - Teks: "reset dong" -> {{"intent": "request_reset"}}
        - Teks: "halo bot" -> {{"intent": "greeting"}}
        - Teks: "cuaca hari ini gimana" -> {{"intent": "unknown"}}

        Hanya kembalikan JSON yang valid.
        """
        response = gemini_model.generate_content(prompt)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '')
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

    # Kembali ke state routing untuk menunggu pesan berikutnya
    return ROUTING


# --- Fungsi Logika Bisnis ---

async def process_new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_data: dict):
    """Menyimpan transaksi baru ke database dan mengirim konfirmasi."""
    user_id = update.effective_user.id

    transaction_type = transaction_data.get("type")
    amount = transaction_data.get("amount")
    description = transaction_data.get("description")

    # Validasi data dari Gemini
    if transaction_type in ["income", "expense"] and isinstance(amount, (int, float)) and amount > 0 and description:
        try:
            # Simpan ke Supabase
            payload = { "user_id": user_id, "type": transaction_type, "amount": amount, "description": description }
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
                    f"<b>Deskripsi:</b> {description}\n\n"
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan sesi edit yang sedang berlangsung dan kembali ke state utama."""
    if 'edit_transaction_id' in context.user_data:
        context.user_data.pop('edit_transaction_id', None)
        context.user_data.pop('original_trx', None)
        context.user_data.pop('original_message_id', None)
        await update.message.reply_text("Mode edit dibatalkan.")
    else:
        await update.message.reply_text("Tidak ada aksi yang sedang berlangsung untuk dibatalkan.")

    return ROUTING

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
        # Prompt AI khusus untuk menginterpretasikan koreksi
        edit_prompt = f"""
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
        response = gemini_model.generate_content(edit_prompt)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '')
        data = json.loads(cleaned_response_text)

        new_amount = data.get("amount")
        new_description = data.get("description")

        if isinstance(new_amount, (int, float)) and new_description:
            # Dapatkan tipe transaksi lama, karena tipe tidak bisa diubah
            original_type_response = supabase.table("transactions").select("type").eq("id", edit_transaction_id).single().execute()
            transaction_type = original_type_response.data['type']

            payload = {"amount": new_amount, "description": new_description}
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
                f"<b>Deskripsi:</b> {new_description}\n\n"
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

    # Bersihkan state setelah selesai
    context.user_data.pop('edit_transaction_id', None)
    context.user_data.pop('original_trx', None)
    context.user_data.pop('original_message_id', None)
    return ROUTING

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menangani semua aksi dari tombol inline secara lebih andal."""
    query = update.callback_query
    await query.answer()  # Memberitahu Telegram bahwa tombol sudah diproses

    user_id = query.from_user.id
    parts = query.data.split(":", 1)
    action = parts[0]
    value = parts[1] if len(parts) > 1 else None

    if not value:
        await query.edit_message_text(text="Error: Aksi dari tombol tidak valid.")
        return

    if action == "edit" or action == "delete":
        try:
            transaction_id = int(value)
        except (ValueError, TypeError):
            await query.edit_message_text(text="Error: ID transaksi pada tombol tidak valid.")
            return

        if action == "edit":
            # Ambil data transaksi lama untuk diberikan sebagai konteks ke AI
            try:
                original_trx_response = supabase.table("transactions").select("description, amount").eq("id", transaction_id).eq("user_id", user_id).single().execute()
                if not original_trx_response.data:
                    await query.edit_message_text("Error: Transaksi asli tidak ditemukan.")
                    return

                context.user_data['edit_transaction_id'] = transaction_id
                context.user_data['original_message_id'] = query.message.message_id
                context.user_data['original_trx'] = original_trx_response.data

                await query.message.reply_text(
                    "<b>Mode Edit Aktif.</b>\n"
                    "Kirimkan koreksi Anda (misal: 'salah, harusnya 15rb' atau 'deskripsinya jadi beli makan malam').\n"
                    "Ketik /cancel untuk membatalkan.",
                    parse_mode='HTML'
                )
                return AWAITING_EDIT_INPUT
            except Exception as e:
                logger.error(f"Error fetching transaction for edit: {e}")
                await query.edit_message_text("Maaf, terjadi kesalahan saat mencoba mengedit.")
                return

        elif action == "delete":
            try:
                delete_response = supabase.table("transactions").delete().match({'id': transaction_id, 'user_id': user_id}).execute()
                if delete_response.data:
                    rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
                    current_balance = rpc_response.data if rpc_response.data is not None else 0
                    deleted_amount = delete_response.data[0]['amount']
                    deleted_desc = delete_response.data[0]['description']
                    await query.edit_message_text(
                        text=f"<s>- - - - - - - - - - - - - - -</s>\n"
                             f"❌ <b>Transaksi Dihapus</b>\n"
                             f"<b>Deskripsi:</b> {deleted_desc}\n"
                             f"<b>Jumlah:</b> Rp{deleted_amount:,.0f}\n"
                             f"<s>- - - - - - - - - - - - - - -</s>\n"
                             f"💰 <b>Saldo Anda sekarang: Rp{current_balance:,.0f}</b>",
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_text(text="Gagal menghapus: Transaksi tidak ditemukan atau Anda tidak punya hak akses.")
            except Exception as e:
                logger.error(f"Error deleting transaction: {e}")
                await query.edit_message_text(text="Maaf, terjadi kesalahan saat mencoba menghapus transaksi.")
            return ROUTING

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
        return ROUTING



# --- Fungsi Utama Bot ---

def main() -> None:
    """Mulai bot Telegram."""
    # Buat aplikasi bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Rombak total ConversationHandler untuk alur yang lebih stabil
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ROUTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_handler),
            ],
            AWAITING_EDIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_input),
                CallbackQueryHandler(button_handler), # Izinkan tombol (misal: hapus) bahkan saat mode edit
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_message=False,
        allow_reentry=True,
    )

    # Daftarkan hanya ConversationHandler sebagai handler utama
    application.add_handler(conv_handler)

    # Mulai bot (polling)
    logger.info("Bot dimulai...")
    application.run_polling()


if __name__ == '__main__':
    main()
