import os
import random
import asyncio
import html
from datetime import datetime

from handlers.admin import maintenance_guard, track_user
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import OWNER_ID

# =======================
# STATES
# =======================
EMAIL, JUMLAH = range(2)

# =======================
# CORE LOGIC
# =======================
def randomize_case(email: str, limit: int):
    results = set()
    letters = sum(1 for c in email if c.isalpha())
    max_p = 2 ** letters
    actual_limit = min(limit, max_p)

    attempt = 0
    while len(results) < actual_limit and attempt < actual_limit * 10:
        res = "".join(
            c.upper() if random.choice([True, False]) else c.lower()
            for c in email
        )
        results.add(res)
        attempt += 1

    return list(results)


# =======================
# /generate
# =======================
async def start_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await maintenance_guard(update, context):
        return

    track_user(update, context, "generate")
    uid = str(update.effective_user.id)
    await update.message.reply_text(
        "📧 **Kirimkan Gmail yang ingin diacak:**",
        parse_mode="Markdown",
    )
    return EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["target"] = update.message.text.strip()
    await update.message.reply_text(
        "🔢 **Berapa jumlah variasi?**",
        parse_mode="Markdown",
    )
    return JUMLAH


async def get_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        await update.message.reply_text("❌ Masukkan angka!")
        return JUMLAH

    uid = str(update.effective_user.id)
    uname = update.effective_user.username or "Tanpa_Username"

    email = context.user_data["target"]
    jumlah = int(update.message.text)

    # =======================
    # LIMIT & NOTIF ADMIN
    # =======================
    if jumlah > 2000:
        await update.message.reply_text(
            "⚠️ **Maksimal generate adalah 2000 variasi.**",
            parse_mode="Markdown",
        )

        notif = (
            "🔔 <b>PERMINTAAN DITOLAK (>2000)</b>\n"
            f"👤 User: @{html.escape(uname)} (<code>{uid}</code>)\n"
            f"📊 Jumlah: <code>{jumlah}</code>"
        )
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=notif,
                parse_mode="HTML",
            )
        except:
            pass

        context.user_data.clear()
        return ConversationHandler.END

    if jumlah > 1500:
        notif = (
            "🔔 <b>GENERATE BESAR (1500-2000)</b>\n"
            f"👤 User: @{html.escape(uname)} (<code>{uid}</code>)\n"
            f"📊 Jumlah: <code>{jumlah}</code>"
        )
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=notif,
                parse_mode="Markdown",
            )
        except:
            pass

    # =======================
    # PROGRESS
    # =======================
    status = await update.message.reply_text(
        "⚙️ **Mempersiapkan proses...**",
        parse_mode="Markdown",
    )

    await asyncio.sleep(0.5)
    await status.edit_text(
        "⏳ **Proses: [▓▓░░░░░░░░] 20%**\n_Mengacak casing..._",
        parse_mode="Markdown",
    )

    hasil = randomize_case(email, jumlah)
    total = len(hasil)

    await asyncio.sleep(0.5)
    await status.edit_text(
        "⏳ **Proses: [▓▓▓▓▓▓░░░░] 60%**\n_Menyusun file..._",
        parse_mode="Markdown",
    )

    # =======================
    # STATISTIK
    # =======================
    if uid in context.bot_data["users"]:
        context.bot_data["users"][uid]["total_gen"] += total

    today = datetime.now().strftime("%Y-%m-%d")
    context.bot_data["history"][today] = (
        context.bot_data["history"].get(today, 0) + total
    )

    await asyncio.sleep(0.5)
    await status.edit_text(
        "⏳ **Proses: [▓▓▓▓▓▓▓▓▓▓] 100%**\n_Mengirim file..._",
        parse_mode="Markdown",
    )

    uid = str(update.effective_user.id)
    context.application.bot_data.setdefault("generate", {
        "users": [],
        "total_generated": 0
    })

    gen = context.application.bot_data["generate"]
    if uid not in gen["users"]:
        gen["users"].append(uid)

    gen["total_generated"] += total
    # =======================
    # OUTPUT FILE
    # =======================
    fname = f"generator_{uid}_{int(datetime.now().timestamp())}.txt"

    try:
        with open(fname, "w") as f:
            f.write("\n".join(hasil))

        caption = (
            "✨ **GENERATE COMPLITE** ✨\n"
            "──────────────────\n"
            f"📧 Source: `{email}`\n"
            f"📊 Variasi: `{total}`\n"
            f"📈 Status: Succes ✅\n"
            "──────────────────\n"
            "🚀 File siap digunakan!"
        )

        with open(fname, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=caption,
                parse_mode="Markdown",
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    finally:
        await status.delete()
        if os.path.exists(fname):
            os.remove(fname)

    context.user_data.clear()
    return ConversationHandler.END


# =======================
# /cancel
# =======================
async def cancel_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Generate dibatalkan.")
    return ConversationHandler.END


# =======================
# SETUP HANDLER (INI KUNCI)
# =======================
def setup(app):
    gen_conv = ConversationHandler(
        entry_points=[CommandHandler("generate", start_gen)],
        states={
            EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)
            ],
            JUMLAH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_jumlah)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_gen)],
        allow_reentry=True,
    )

    app.add_handler(gen_conv)

