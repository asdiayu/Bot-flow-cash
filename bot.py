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
    """Fungsi utama yang menangani semua pesan teks dan bertindak sebagai router."""
    user_text = update.message.text

    # Kirim pesan bahwa bot sedang bekerja
    processing_message = await update.message.reply_text("🧠 Berpikir...")

    try:
        # Prompt untuk Gemini AI V2 - Router Intent
        prompt = f"""
        Anda adalah AI pusat untuk bot keuangan. Tugas Anda adalah menganalisis teks pengguna dan mengklasifikasikannya ke dalam salah satu "intent" berikut: "log_transaction", "query_summary", "greeting", atau "unknown".
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

        3.  Jika intentnya `greeting` (sapaan), formatnya:
            {{"intent": "greeting"}}

        4.  Jika tidak cocok sama sekali, formatnya:
            {{"intent": "unknown"}}

        --- CONTOH ---
        - Teks: "beli kopi 25000" -> {{"intent": "log_transaction", "transaction": {{"type": "expense", "amount": 25000, "description": "beli kopi"}}}}
        - Teks: "dapat gaji 5jt" -> {{"intent": "log_transaction", "transaction": {{"type": "income", "amount": 5000000, "description": "dapat gaji"}}}}
        - Teks: "summary hari ini" -> {{"intent": "query_summary", "query": {{"period": "today", "type": "all"}}}}
        - Teks: "laporan bulan ini" -> {{"intent": "query_summary", "query": {{"period": "this_month", "type": "all"}}}}
        - Teks: "cek pengeluaran kemarin" -> {{"intent": "query_summary", "query": {{"period": "yesterday", "type": "expense"}}}}
        - Teks: "pemasukan bulan lalu apa aja?" -> {{"intent": "query_summary", "query": {{"period": "last_month", "type": "income"}}}}
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


# --- Fungsi Handler Lanjutan ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan sesi edit yang sedang berlangsung."""
    context.user_data.pop('edit_transaction_id', None)
    context.user_data.pop('original_message_id', None)
    await update.message.reply_text("Sesi edit dibatalkan.")
    return ConversationHandler.END

async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menangani pesan dari user saat dalam mode edit."""
    user_text = update.message.text
    user_id = update.effective_user.id

    edit_transaction_id = context.user_data.get('edit_transaction_id')
    if not edit_transaction_id:
        await update.message.reply_text("Error: Tidak ada sesi edit yang aktif. Silakan mulai lagi.")
        return ConversationHandler.END

    # Kirim pesan bahwa bot sedang bekerja
    processing_message = await update.message.reply_text("🧠 Menganalisis editan Anda...")

    try:
        # Gunakan prompt yang sama dengan handle_message untuk konsistensi
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
        """
        response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(prompt)
        cleaned_response_text = response.text.strip().replace('```json', '').replace('```', '')
        data = json.loads(cleaned_response_text)

        transaction_type = data.get("type")
        amount = data.get("amount")
        description = data.get("description")

        if transaction_type in ["income", "expense"] and isinstance(amount, (int, float)) and amount > 0:
            payload = {"type": transaction_type, "amount": amount, "description": description}
            # Lakukan UPDATE, bukan INSERT
            db_response = supabase.table("transactions").update(payload).eq("id", edit_transaction_id).eq("user_id", user_id).execute()

            # Ambil ID pesan asli untuk diedit
            original_message_id = context.user_data.get('original_message_id')
            await processing_message.delete() # Hapus pesan "menganalisis..."

            # Hitung ulang saldo
            rpc_response = supabase.rpc('calculate_balance', {'p_user_id': user_id}).execute()
            current_balance = rpc_response.data if rpc_response.data is not None else 0

            # Buat keyboard lagi
            keyboard = [[
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{edit_transaction_id}"),
                InlineKeyboardButton("❌ Hapus", callback_data=f"delete:{edit_transaction_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Buat teks konfirmasi baru
            confirmation_text = (
                f"✅ <b>Transaksi Diperbarui!</b>\n\n"
                f"<b>Jenis:</b> {'Pemasukan' if transaction_type == 'income' else 'Pengeluaran'}\n"
                f"<b>Jumlah:</b> Rp{amount:,.0f}\n"
                f"<b>Deskripsi:</b> {description}\n\n"
                f"💰 <b>Saldo Anda saat ini: Rp{current_balance:,.0f}</b>"
            )

            # Edit pesan asli
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=original_message_id,
                text=confirmation_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )

            # Bersihkan state dan akhiri conversation
            context.user_data.pop('edit_transaction_id', None)
            context.user_data.pop('original_message_id', None)
            return ConversationHandler.END
        else:
            await processing_message.edit_text("Hmm, sepertinya itu bukan transaksi keuangan. Silakan coba lagi atau batalkan dengan /cancel.")
            return AWAITING_EDIT_INPUT # Tetap di mode edit

    except Exception as e:
        logger.error(f"Error processing edit input: {e}")
        await processing_message.edit_text("Maaf, terjadi kesalahan saat memproses editan Anda.")
        context.user_data.pop('edit_transaction_id', None)
        context.user_data.pop('original_message_id', None)
        return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani semua aksi dari tombol inline."""
    query = update.callback_query
    await query.answer()  # Memberitahu Telegram bahwa tombol sudah diproses

    # Parsing data dari tombol, format: "aksi:id_transaksi"
    try:
        action, transaction_id_str = query.data.split(":")
        transaction_id = int(transaction_id_str)
    except (ValueError, IndexError):
        await query.edit_message_text(text="Error: Data dari tombol tidak valid.")
        return

    user_id = query.from_user.id

    if action == "edit":
        # Simpan ID transaksi yang akan diedit di user_data
        context.user_data['edit_transaction_id'] = transaction_id
        # Simpan juga ID pesan asli agar bisa kita edit nanti
        context.user_data['original_message_id'] = query.message.message_id

        await query.message.reply_text("Silakan kirim detail transaksi yang baru...")
        return AWAITING_EDIT_INPUT

    elif action == "delete":
        try:
            # Hapus transaksi, pastikan user_id cocok untuk keamanan
            delete_response = supabase.table("transactions").delete().match({'id': transaction_id, 'user_id': user_id}).execute()

            if delete_response.data:
                # Hitung ulang saldo setelah dihapus
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



# --- Fungsi Utama Bot ---

def main() -> None:
    """Mulai bot Telegram."""
    # Buat aplikasi bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Buat ConversationHandler untuk mengelola state
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(button_handler) # Tombol sekarang bagian dari percakapan
        ],
        states={
            AWAITING_EDIT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_input)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel), # Hanya /cancel yang merupakan fallback dari conversation
        ],
        per_user=True,
        per_message=False,
        allow_reentry=True
    )

    # Daftarkan handler
    application.add_handler(CommandHandler("start", start)) # /start adalah perintah global
    application.add_handler(conv_handler) # Conversation handler untuk alur utama


    # Mulai bot (polling)
    logger.info("Bot dimulai...")
    application.run_polling()


if __name__ == '__main__':
    main()
