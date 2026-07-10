import time
import html
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.errors import FloodWaitError
from telethon import types
from keyboards.owner import kb_owner
from services.userbot import client
from storage.entity_cache import add   # ✅ BENAR
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.admin import maintenance_guard

# ===============================
# GLOBAL COOLDOWN (ANTI FLOOD)
# ===============================
_LAST_RESOLVE = 0
RESOLVE_COOLDOWN = 15  # detik


def safe(t):
    return html.escape(str(t)) if t else "-"


async def cekid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _LAST_RESOLVE

    if not await maintenance_guard(update, context):
        return

    msg = update.message

    if not context.args:
        await msg.reply_text(
            "💡 <b>Cara pakai /cekid</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• <code>/cekid @username</code>\n"
            "• <code>/cekid https://t.me/username</code>\n\n"
            "<i>Kirim link channel atau group</i>",
            parse_mode="HTML"
        )
        return

    raw = context.args[0]

    # ===============================
    # NORMALISASI USERNAME
    # ===============================
    if raw.startswith("https://t.me/"):
        username = raw.replace("https://t.me/", "").split("/")[0]
    elif raw.startswith("@"):
        username = raw[1:]
    else:
        await msg.reply_text(
            "❌ Gunakan @username atau link yang valid",
            reply_markup=kb_owner(),
            parse_mode="HTML"
        )
        return

    # ===============================
    # HARD COOLDOWN
    # ===============================
    now = time.time()
    if now - _LAST_RESOLVE < RESOLVE_COOLDOWN:
        await msg.reply_text(
            f"⏳ Tunggu {int(RESOLVE_COOLDOWN - (now - _LAST_RESOLVE))} detik",
            parse_mode="HTML"
        )
        return

    _LAST_RESOLVE = now

    loading = await msg.reply_text("🔍 <i>Resolving entity...</i>", parse_mode="HTML")

    try:
        # ===============================
        # SATU-SATUNYA TEMPAT RESOLVE
        # ===============================
        result = await client(
            ResolveUsernameRequest(username=username)
        )

        entity = None
        if result.chats:
            entity = result.chats[0]
        elif result.users:
            entity = result.users[0]

        if not entity or not isinstance(entity, (types.Chat, types.Channel)):
            raise ValueError("Bukan grup / channel")

        # ✅ ADVANCED CACHE (BENAR)
        add(entity)

        await loading.edit_text(
            f" 📛 <b>Name</b> : {safe(getattr(entity, 'title', '-'))}\n"
            f" 🆔 <b>ID</b>    : <code>-100{entity.id}</code>\n"
            f" 🔗 <b>Username</b> : @{safe(entity.username) if entity.username else '-'}\n"
            f" 🔐 <b>Type</b>  : {'Private' if entity.username is None else 'Public'}\n\n"
            "<i>Gunakan /cinfo dengan ID atau username</i>",
            parse_mode="HTML"
        )

    except FloodWaitError as e:
        await loading.edit_text(
            f"🚫 <b>FloodWait</b>\nTunggu {e.seconds} detik",
            parse_mode="HTML"
        )

    except Exception as e:
        await loading.edit_text(
            "❌ <i>Gagal resolve :</i>\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML"
        )


def setup(app):
    app.add_handler(CommandHandler("cekid", cekid_cmd))

