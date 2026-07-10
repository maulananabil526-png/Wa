from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
import html

from services.userbot import get_real_dc, client as userbot
from telethon import functions, types

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Ambil DC ID via Userbot service
    try:
        u = await userbot.get_entity(user.id)
        dc_id = u.photo.dc_id if u.photo else "Unknown"
    except:
        dc_id = "unknow"

    # Escape HTML untuk user input
    full_name = html.escape(user.full_name or "Unknown")
    username = html.escape(user.username or "-")
    
    text = (
        f"👋 <b>Halo!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 » <b>NAME</b> : {full_name}\n"
        f"🆔 » <b>USER ID</b> : <code>{user.id}</code>\n"
        f"🗣️ » <b>USERNAME</b> : @{username}\n"
        f"🌐 » <b>DC ID</b> : <code>{dc_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <i>Silakan gunakan menu di bawah untuk fitur lainnya.</i>"
    )

    try:
        photos = await context.bot.get_user_profile_photos(user.id)
        if photos.total_count > 0:
            await update.message.reply_photo(
                photo=photos.photos[0][-1].file_id,
                caption=text,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text, parse_mode="HTML")


def setup(app):
    app.add_handler(CommandHandler("start", start_cmd))

