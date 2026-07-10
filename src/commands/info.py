from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from services.userbot import client as userbot

from telethon import functions, types
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.errors import FloodWaitError
from handlers.admin import maintenance_guard

import asyncio
import os
import html   # ✅ [TAMBAHAN] untuk escape HTML


# ==================================================
# ✅ [TAMBAHAN] SAFE HTML (ANTI BIO ANEH / SILENT)
# ==================================================
def safe_html(text: str) -> str:
    if not text:
        return "-"
    return html.escape(str(text))


# ==================================================
# SAFE CALL (AUTO RETRY + ANTI FLOOD)
# ==================================================
async def safe_call(func, retries=3):
    for i in range(retries):
        try:
            return await func()
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except asyncio.TimeoutError:
            if i == retries - 1:
                raise
            await asyncio.sleep(1.5)
        except Exception:
            if i == retries - 1:
                raise
            await asyncio.sleep(1)


# ==================================================
# RESOLVE TARGET (STABLE)
# ==================================================
async def resolve_target(target):
    try:
        return await safe_call(lambda: userbot.get_entity(target))
    except Exception:
        pass

    try:
        result = await safe_call(
            lambda: userbot(ResolveUsernameRequest(target))
        )
        if result.users:
            return result.users[0]
        raise Exception("User tidak ditemukan")
    except Exception as e:
        raise Exception(f"Gagal resolve user: {e}")


# ==================================================
# COMMAND /info
# ==================================================
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await maintenance_guard(update, context):
        return
    msg = update.message
    target = None

    # ===============================
    # AMBIL TARGET
    # ===============================
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user.id
    elif context.args:
        arg = context.args[0]
        if arg.isdigit():
            target = int(arg)
        else:
            target = arg.lstrip("@")

    if not target:
        await msg.reply_text(
            "💡 <b>Cara menggunakan /info</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            " ❒ <code>/info &lt;user_id&gt;</code>\n"
            " ❒ <code>/info @username</code>\n"
            " ❒ Reply pesan user lalu <code>/info</code>\n"
            "━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML"
        )
        return

    load = await msg.reply_text(
        "📡 <i>Decrypting User Data...</i>",
        parse_mode="HTML"
    )

    try:
        # ===============================
        # RESOLVE USER
        # ===============================
        u = await resolve_target(target)
        is_bot = bool(u.bot)

        # ===============================
        # GET FULL USER (USER & BOT DIPERLAKUKAN SAMA)
        # ===============================
        full = None
        try:
            full = await safe_call(
                lambda: userbot(
                    functions.users.GetFullUserRequest(id=u.id)
                )
            )
        except Exception:
            full = None

        # ===============================
        # DC ID
        # ===============================
        dc_id = "Hidden"
        if u.photo and hasattr(u.photo, "dc_id"):
            dc_id = u.photo.dc_id

        # ===============================
        # BIO (SAFE)
        # ===============================
        bio = (
            full.full_user.about
            if full and full.full_user and full.full_user.about
            else "No description available."
        )

        # ===============================
        # STATUS
        # ===============================
        status_map = {
            types.UserStatusOnline: "🟢 ACTIVE",
            types.UserStatusOffline: "⚪ OFFLINE",
        }
        current_status = next(
            (v for k, v in status_map.items() if isinstance(u.status, k)),
            "🟡 RECENTLY"
        )

        # ===============================
        # LINK
        # ===============================
        identity_link = (
            f"https://t.me/{u.username}"
            if u.username
            else f"tg://user?id={u.id}"
        )

        # ===============================
        # FORMAT OUTPUT (HTML SAFE)
        # ===============================
        text = (
            "💠 <b>USER DIGITAL IDENTITY</b> 💠\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"  » <b>USER ID</b>  : <code>{u.id}</code>\n"
            f"  » <b>FULL NAME</b>: {safe_html(u.first_name)} {safe_html(u.last_name)}\n"
            f"  » <b>USERNAME</b> : @{safe_html(u.username or 'none')}\n"
            f"  » <b>IS BOT</b>   : {str(is_bot).upper()}\n"
            f"  » <b>DC ID</b>    : {dc_id}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"  ◈ <b>PREMIUM</b>  : {'✅ Yes' if getattr(u, 'premium', False) else '❌ No'}\n"
            f"  ◈ <b>VERIFIED</b> : {'🛡️ Trusted' if u.verified else '👤 Standard'}\n"
            f"  ◈ <b>INTEGRITY</b>: {'⚠️ Suspicious' if u.scam else '✅ Clean'}\n"
            f"  ◈ <b>STATUS</b>   : {current_status}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 <b>BIO:</b>\n<i>{safe_html(bio)}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href=\"{identity_link}\">IDENTITY LINK</a>"
        )

        # ===============================
        # FOTO (JANGAN DIPAKSA)
        # ===============================
        photos = []
        try:
            photos = await safe_call(
                lambda: userbot.get_profile_photos(u.id, limit=1)
            )
        except Exception:
            photos = []

        await load.delete()

        if photos:
            path = None
            try:
                path = await userbot.download_media(photos[0])
                await msg.reply_photo(
                    photo=open(path, "rb"),
                    caption=text,
                    parse_mode="HTML"
                )
            except Exception:
                await msg.reply_text(text, parse_mode="HTML")
            finally:
                if path and os.path.exists(path):
                    os.remove(path)
        else:
            await msg.reply_text(text, parse_mode="HTML")

    except Exception as e:
        try:
            await load.edit_text(
                f"❌ <b>Failed to retrieve identity</b>\n<code>{safe_html(e)}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ==================================================
# SETUP
# ==================================================
def setup(app):
    app.add_handler(CommandHandler(["info", "userinfo"], user_info))

