import os
import html
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telethon import functions, types
from telethon.tl.types import InputChannel
from services.userbot import client, get_channel_photo
from storage.entity_cache import get
from handlers.admin import maintenance_guard

def safe(t):
    return html.escape(str(t)) if t else "-"

async def cinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await maintenance_guard(update, context):
        return
    msg = update.message

    if not context.args:
        await msg.reply_text(
            "💡 <b>Cara pakai /cinfo</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• <code>/cinfo @username</code>\n"
            "• <code>/cinfo -100xxxxxxxx</code>\n\n"
            "<i>Kirim usename Group atau ID</i>",
            parse_mode="HTML"
        )
        return

    target = context.args[0]

    # 🔒 BLOK LINK
    if target.startswith("http"):
        await msg.reply_text(
            "🚫 <i> Link tidak didukung !</i>\n"
            f"<i>gunakan link Channel atau username Group</i>",
            parse_mode="HTML"
        )
        return

    try:
        # ===============================
        # ID MODE (ADVANCED CACHE)
        # ===============================
        if target.startswith("-100"):
            cached = get(target)
            if not cached:
                await msg.reply_text(
                    "🚫 <i>gagal mengambil info !</i> \n"
                    f"<i>gunakan username atau</i> /cekid <i>dahulu</i>  ",
                    parse_mode="HTML"
                )
                return

            if cached["private"]:
                entity_input = InputChannel(
                    channel_id=cached["id"],
                    access_hash=cached["access_hash"]
                )
            else:
                entity_input = f"@{cached['username']}"

        # ===============================
        # USERNAME MODE
        # ===============================
        else:
            entity_input = target

        loading = await msg.reply_text("📡 <i>Mengambil info...</i>", parse_mode="HTML")

        entity = await client.get_entity(entity_input)

        if not isinstance(entity, (types.Chat, types.Channel)):
            raise ValueError("Bukan grup / channel")

        full = await client(
            functions.channels.GetFullChannelRequest(entity)
        )

        type_name = "Group" if getattr(entity, "megagroup", False) else "Channel"

        text = (
            "📢 <b>CHANNEL / GROUP INFORMATION</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>ID</b>        : <code>-100{entity.id}</code>\n"
            f"📛 <b>Name</b>     : {safe(entity.title)}\n"
            f"💬 <b>Type</b>     : {type_name}\n"
            f"🔗 <b>Username</b>  : @{safe(entity.username) if entity.username else '-'}\n"
            f"👥 <b>Members</b>   : {full.full_chat.participants_count}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <b>Verified</b>  : {'Yes' if entity.verified else 'No'}\n"
            f"⚠️ <b>Scam</b>      : {'Yes' if entity.scam else 'No'}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 <b>Description</b>:\n"
            f"<i>{safe(full.full_chat.about)}</i>"
        )

        await loading.delete()

        # ===============================
        # FOTO (AMAN PUBLIC / PRIVATE)
        # ===============================
        photo_path = await get_channel_photo(entity=entity)

        if photo_path and os.path.exists(photo_path):
            try:
                with open(photo_path, "rb") as f:
                    await msg.reply_photo(f, caption=text, parse_mode="HTML")
            finally:
                os.remove(photo_path)
        else:
            await msg.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await msg.reply_text(
            "❌ <b>Gagal mengambil info</b>\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML"
        )


def setup(app):
    app.add_handler(CommandHandler("cinfo", cinfo_cmd))

