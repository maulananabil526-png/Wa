import os
import json
import time
import psutil
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler
)
from config import OWNER_ID, OWNER_USERNAME

BASE_DIR = "storage"
ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
BANNED_FILE = os.path.join(BASE_DIR, "banned_users.json")
ADMIN_LOG = os.path.join(BASE_DIR, "admin_log.txt")
MAINTENANCE_FILE = "storage/maintenance.json"
ENTITY_CACHE_FILES = ["storage/entity_cache.json"]
BOT_START_TIME = time.monotonic()

# ============= HELPER ================
def format_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"

def detect_runtime():
   if os.path.exists("/data/data/com.termux"):
     return "TERMUX"
   return "VPS"
def get_userbot_status(context):
    ub = context.application.bot_data.get("userbot")
    if not ub:
        return "DISCONNECTED", "-", "-"
    return ub.get("status"), ub.get("me", "-"), ub.get("dc", "-")

def format_size(bytes_size):
    if bytes_size < 1024 * 1024:
        kb = bytes_size / 1024
        return f"{kb:.2f} KB"
    else:
        mb = bytes_size / (1024 * 1024)
        return f"{mb:.2f} MB"

def get_maintenance():
    if not os.path.exists(MAINTENANCE_FILE):
        return False

    try:
        with open(MAINTENANCE_FILE, "r") as f:
            data = json.load(f)
        return bool(data.get("enabled", False))
    except Exception:
        return False

def toggle_maintenance():
    current = get_maintenance()
    new_status = not current

    os.makedirs(os.path.dirname(MAINTENANCE_FILE), exist_ok=True)

    with open(MAINTENANCE_FILE, "w") as f:
        json.dump(
            {
                "enabled": new_status,
                "since": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            f,
            indent=2,
        )

    return new_status

def is_banned(user_id: int) -> bool:
    if not os.path.exists(BANNED_FILE):
        return False
    with open(BANNED_FILE) as f:
        data = json.load(f)
    return str(user_id) in data

def clear_entity_cache():
    total_size = 0
    total_files = 0

    for path in ENTITY_CACHE_FILES:
        if os.path.exists(path):
            total_size += os.path.getsize(path)
            os.remove(path)
            total_files += 1

    return total_files, total_size

def get_entity_cache_info():
    total_size = 0
    total_files = 0

    for path in ENTITY_CACHE_FILES:
        if os.path.exists(path):
            total_size += os.path.getsize(path)
            total_files += 1

    return total_files, total_size

def get_entity_cache_total():
    path = os.path.join("storage", "entity_cache.json")

    if not os.path.exists(path):
        return 0

    try:
        with open(path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return len(data)
    except Exception:
        pass

    return 0
def get_entity_cache_kb():
    path = "storage/entity_cache.json"
    if not os.path.exists(path):
        return 0
    return os.path.getsize(path) / 1024

def track_user(update, context, feature: str = None):
    try:
        user = update.effective_user
        if not user:
            return

        uid = str(user.id)
        now = time.time()

        # ===== USERS GLOBAL =====
        users = context.application.bot_data.setdefault("users", {})
        users.setdefault(uid, {
            "first_seen": now,
            "last_active": now,
            "total_gen": 0
        })
        users[uid]["last_active"] = now

        # ===== CEKBIO TRACK =====
        if feature == "cekbio":
            data = context.application.bot_data.setdefault("cekbio", {
                "senders": [],
                "total_checked": 0,
                "daily_checked": 0
            })

            if uid not in data["senders"]:
                data["senders"].append(uid)

        # ===== GENERATE TRACK =====
        elif feature == "generate":
            data = context.application.bot_data.setdefault("generate", {
                "users": [],
                "total_generated": 0
            })

            if uid not in data["users"]:
                data["users"].append(uid)

    except Exception as e:
        print("track_user error:", e)

#=================== KYBOARD ==================
def admin_dashboard_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Feature", callback_data="admin_feature"),
            InlineKeyboardButton("👤 Info Users", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton("📡 Status", callback_data="admin_status"),
            InlineKeyboardButton("🛠️ Setting", callback_data="admin_setting"),
        ]
    ])

def back_dashboard_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Kembali", callback_data="admin_dashboard")]
    ])
def admin_status_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛠 MT ON / OFF", callback_data="admin_mt_confirm"),
            InlineKeyboardButton("🧹 Clear Entity", callback_data="admin_clear_cache_confirm"),
        ],
        [
            InlineKeyboardButton("⬅️ Kembali", callback_data="admin_dashboard"),
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_status_refresh"),
        ],
    ])
def admin_mt_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ya, Toggle MT", callback_data="admin_mt_toggle")],
        [InlineKeyboardButton("❌ Batal", callback_data="admin_status")],
    ])


def admin_clear_cache_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Ya, Bersihkan Cache", callback_data="admin_clear_cache")],
        [InlineKeyboardButton("❌ Batal", callback_data="admin_status")],
    ])
def admin_info_users_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Kembali", callback_data="admin_dashboard"),
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_users"),
        ],
    ])
# =========================
# Views (Text Only)
# =========================

DASHBOARD_TEXT = (
    "🛡️ *ADMIN PANEL*\n"
    "━━━━━━━━━━━━━━\n"
    "📊 Monitor Bot\n"
    "_(coming soon)_"
)

FEATURE_TEXT = (
    "⚙️ *FEATURE ADMIN*\n"
    "━━━━━━━━━━━━━━\n"
    "/admin add <id>  ➜ tambah admin\n"
    "/admin del <id>  ➜ hapus admin\n"
    "/admin list      ➜ list admin\n\n"
    "/ban <id> [reason]   ➜ ban user\n"
    "/unban <id>          ➜ unban user\n\n"
    "/feature <x> on|off  ➜ toggle fitur\n"
    "/limit <x> <n>       ➜ set limit\n"
    "/maintenance on/off  ➜ maintenance"
)

SETTING_TEXT = (
    "🛠️ *BOT SETTING*\n"
    "━━━━━━━━━━━━━━\n"
    "/clear cache        ➜ hapus cache\n"
    "/reload config      ➜ reload config\n"
    "/restart bot        ➜ restart bot\n"
    "/reset limit        ➜ reset limit user"
)

# =========================
# Handlers
# =========================
async def maintenance_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # OWNER BYPASS
    if update.effective_user and update.effective_user.id == OWNER_ID:
        return True

    if not get_maintenance():
        return True

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

    try:
        if update.message:
            await update.message.reply_text(
                "🛠 *Bot sedang maintenance*\n\n"
                "Silakan coba lagi nanti.",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "Bot sedang maintenance",
                show_alert=True,
            )
    except Exception:
        pass

    return False
# ================== TEKS BUilDER ==================
async def build_info_users_overview(context):
    # ===== Ambil data dengan aman =====
    users = context.application.bot_data.get("users") or {}
    premium = context.application.bot_data.get("premium_users") or []

    cekbio = context.application.bot_data.get("cekbio") or {}
    generate = context.application.bot_data.get("generate") or {}

    # ===== Pastikan tipe data LIST =====
    premium = list(premium) if isinstance(premium, (list, set)) else []

    senders = cekbio.get("senders") or []
    senders = list(senders) if isinstance(senders, (list, set)) else []

    gen_users_list = generate.get("users") or []
    gen_users_list = list(gen_users_list) if isinstance(gen_users_list, (list, set)) else []

    now = time.time()

    # ===== Statistik BOT =====
    total_users = len(users)
    active_users = sum(
        1 for u in users.values()
        if isinstance(u, dict) and now - u.get("last_active", 0) < 86400
    )
    premium_users = len(premium)

    # ===== Statistik CEKBIO =====
    total_senders = len(senders)
    sender_active = total_senders  # sementara
    total_checked = int(cekbio.get("total_checked", 0))
    daily_checked = int(cekbio.get("daily_checked", 0))

    # ===== Statistik GENERATE =====
    gen_users = len(gen_users_list)
    total_generated = int(generate.get("total_generated", 0))

    # ===== Output =====
    return (
        "👥 *INFO USERS — OVERVIEW*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 *BOT*\n"
        f"• Total pengguna bot      : `{total_users}`\n"
        f"• User aktif (24 jam)     : `{active_users}`\n"
        f"• User premium            : `{premium_users}`\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📲 *CEKBIO WHATSAPP*\n"
        f"• Total sender terdaftar  : `{total_senders}`\n"
        f"• Sender aktif            : `{sender_active}`\n"
        f"• Total nomor dicek       : `{total_checked}`\n"
        f"• Total nomor dicek/hari  : `{daily_checked}`\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✉️ *GENERATE GMAIL*\n"
        f"• Total pengguna fitur    : `{gen_users}`\n"
        f"• Total email digenerate  : `{total_generated}`\n"
    )

#===== MENU STATUS BOT ======
async def build_status_text(update,context: ContextTypes.DEFAULT_TYPE, ping_ms: int):
    # -------- Bot uptime --------
    uptime = format_uptime(time.monotonic() - BOT_START_TIME)
    runtime = detect_runtime()
    # -------- Telegram API latency --------
    try:
        t0 = time.perf_counter()
        await context.bot.get_me()
        api_latency = f"{int((time.perf_counter() - t0) * 1000)} ms"
    except Exception:
        api_latency = "N/A"

    # -------- RAM --------
    try:
        vm = psutil.virtual_memory()
        ram_total = f"{vm.total / (1024**3):.2f} GB"
        ram_used = f"{vm.used / (1024**3):.2f} GB"
        ram_free = f"{vm.available / (1024**3):.2f} GB"
    except Exception:
        ram_total = ram_used = ram_free = "N/A"

    # -------- CPU --------
    try:
        cpu = f"{psutil.cpu_percent(interval=None)} %"
    except Exception:
        cpu = "N/A"
    # -------- Cache --------
    cache_files, cache_size = get_entity_cache_info()
    total_entity = get_entity_cache_total()
    cache_kb = get_entity_cache_kb()
    # -------- Maintenance --------
    maintenance = "ON" if get_maintenance() else "OFF"
   # --------- userbot status------
    ub_status, ub_me, ub_dc = get_userbot_status(context)
   # ---------- notif bakend ------
    backend = context.application.bot_data.get("backend", {})
    b_status = backend.get("status", "UNKNOWN")
    b_last = backend.get("last_seen", 0)

    if b_last:
       b_last = time.strftime("%H:%M:%S", time.localtime(b_last))
    else:
       b_last = "-"

    return (
        "╭───── ⧼ 𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐔𝐒 ⧽ ───── \n"
        "  🤖*Bot Aktif*\n"
        f" ❒ Uptime           : `{uptime}`\n"
        f" ❒ Ping (internal)        : `{ping_ms} ms`\n"
        f" ❒ Latency Telegram API   : `{api_latency}`\n\n"
        "   🌐 *Backend Cekbio (NodeJS)*\n"
        f" ❒ Status               : `{b_status}`\n"
        f" ❒ Last seen           : `{b_last}`\n\n"
        "  🧠 *System RAM (Android)*\n"
        f" ❒ OS type             : `{runtime}`\n"
        f" ❒ Total RAM         : `{ram_total}`\n"
        f" ❒ Terpakai            : `{ram_used}`\n"
        f" ❒ Sisa                   : `{ram_free}`\n"
        f" ❒ CPU Usage / Core     : `{cpu}`\n\n"
        "   🗂 *Userbot Entity Cache*\n"
        f" ❒ Total entity           :`{total_entity}`\n"
        f" ❒ File                   : `{cache_files}`\n"
        f" ❒ Size                  : `{format_size(cache_size)}` ({cache_kb:.1f} KB)\n\n"
        "   🤖 *Userbot Telegram*\n"
        f" ❒ Status                : `{ub_status}`\n"
        f" ❒ Account              : `{ub_me}`\n"
        f" ❒ DC                     : `{ub_dc}`\n\n"
        "   🛠 *Maintenance*\n"
        f" ❒ Status                 : `{maintenance}`"
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    await update.message.reply_text(
        DASHBOARD_TEXT,
        reply_markup=admin_dashboard_kb(),
        parse_mode="Markdown"
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "admin_dashboard":
        await query.edit_message_text(
            DASHBOARD_TEXT,
            reply_markup=admin_dashboard_kb(),
            parse_mode="Markdown"
        )

    elif data == "admin_feature":
        await query.edit_message_text(
            FEATURE_TEXT,
            reply_markup=back_dashboard_kb(),
            parse_mode="Markdown"
        )

    elif data == "admin_users":
        await query.answer("🔄 Data diperbarui")
        text = await build_info_users_overview(context)
        text += f"\n\n_Refreshed: {time.strftime('%H:%M:%S')}_"

        await query.edit_message_text(
             text,
             reply_markup=admin_info_users_kb(),
             parse_mode="Markdown"
        )

    elif data in ("admin_status", "admin_status_refresh"):
        start = time.perf_counter()
        text = await build_status_text(update, context, 0)
        ping_ms = int((time.perf_counter() - start) * 1000)

        text = await build_status_text(update, context, ping_ms)
        await query.edit_message_text(
            text,
            reply_markup=admin_status_kb(),
            parse_mode="Markdown"
        )

    elif data == "admin_setting":
        await query.edit_message_text(
            SETTING_TEXT,
            reply_markup=back_dashboard_kb(),
            parse_mode="Markdown"
        )
    elif data == "admin_mt_confirm":
        await query.edit_message_text(
            "⚠️ *KONFIRMASI*\n\nAktifkan / Nonaktifkan mode maintenance?",
            reply_markup=admin_mt_confirm_kb(),
            parse_mode="Markdown"
        )

    elif data == "admin_mt_toggle":
        status = toggle_maintenance()
        await query.edit_message_text(
           f"🛠 *Maintenance {'AKTIF' if status else 'NONAKTIF'}*",
           reply_markup=admin_status_kb(),
           parse_mode="Markdown"
        )

    elif data == "admin_clear_cache_confirm":
        await query.edit_message_text(
           "⚠️ *KONFIRMASI*\n\nSemua entity cache userbot akan dihapus.\nTindakan ini tidak bisa dibatalkan.",
           reply_markup=admin_clear_cache_confirm_kb(),
           parse_mode="Markdown"
        )

    elif data == "admin_clear_cache":
        files, size = clear_entity_cache()
        await query.edit_message_text(
           f"🧹 *CACHE DIBERSIHKAN*\n\n"
           f"□ File dihapus : `{files}`\n"
           f"□ Total size   : `{format_size(size)}`",
           reply_markup=admin_status_kb(),
           parse_mode="Markdown"
        )

# =========================
# ADMIN MANAGEMENT
# =========================
def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return [OWNER_ID]
    with open(ADMINS_FILE) as f:
        return json.load(f)

def save_admins(admins):
    os.makedirs(os.path.dirname(ADMINS_FILE), exist_ok=True)
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Format: /admin add <user_id>")
        return
    
    user_id = int(context.args[0])
    admins = load_admins()
    
    if user_id in admins:
        await update.message.reply_text(f"ℹ️ {user_id} sudah admin")
        return
    
    admins.append(user_id)
    save_admins(admins)
    await update.message.reply_text(f"✅ {user_id} ditambah jadi admin")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Format: /admin del <user_id>")
        return
    
    user_id = int(context.args[0])
    if user_id == OWNER_ID:
        await update.message.reply_text("❌ Tidak bisa hapus owner")
        return
    
    admins = load_admins()
    if user_id not in admins:
        await update.message.reply_text(f"ℹ️ {user_id} bukan admin")
        return
    
    admins.remove(user_id)
    save_admins(admins)
    await update.message.reply_text(f"✅ {user_id} dihapus dari admin")

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    admins = load_admins()
    text = "👤 *DAFTAR ADMIN*\n"
    for idx, admin in enumerate(admins, 1):
        text += f"{idx}. `{admin}`\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# =========================
# BAN MANAGEMENT
# =========================
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Format: /ban <user_id> [reason]")
        return
    
    user_id = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Tidak ada alasan"
    
    banned = context.application.bot_data.setdefault("banned", [])
    if user_id in banned:
        await update.message.reply_text(f"ℹ️ {user_id} sudah di-ban")
        return
    
    banned.append(user_id)
    await update.message.reply_text(f"✅ {user_id} di-ban\n📝 Alasan: {reason}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Format: /unban <user_id>")
        return
    
    user_id = int(context.args[0])
    banned = context.application.bot_data.get("banned", [])
    
    if user_id not in banned:
        await update.message.reply_text(f"ℹ️ {user_id} tidak di-ban")
        return
    
    banned.remove(user_id)
    await update.message.reply_text(f"✅ {user_id} di-unban")

# =========================
# FEATURE TOGGLE
# =========================
async def toggle_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Format: /feature <name> on|off")
        return
    
    feature = context.args[0]
    status = context.args[1].lower()
    
    if status not in ["on", "off"]:
        await update.message.reply_text("❌ Status harus 'on' atau 'off'")
        return
    
    features = context.application.bot_data.setdefault("features", {})
    features[feature] = (status == "on")
    
    await update.message.reply_text(f"✅ Feature '{feature}' di-set ke {status.upper()}")

# =========================
# LIMIT MANAGEMENT
# =========================
async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Format: /limit <feature> <number>")
        return
    
    feature = context.args[0]
    try:
        limit = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Limit harus angka")
        return
    
    limits = context.application.bot_data.setdefault("limits", {})
    limits[feature] = limit
    
    await update.message.reply_text(f"✅ Limit '{feature}' di-set ke {limit}")

async def reset_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    context.application.bot_data["limits"] = {}
    await update.message.reply_text("✅ Semua limit direset")

# =========================
# MAINTENANCE
# =========================
async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Format: /maintenance on|off")
        return
    
    status = context.args[0].lower()
    if status == "on":
        toggle_maintenance()
        await update.message.reply_text("🛠 Maintenance mode: ON")
    elif status == "off":
        toggle_maintenance()
        await update.message.reply_text("🛠 Maintenance mode: OFF")
    else:
        await update.message.reply_text("❌ Status harus 'on' atau 'off'")

# =========================
# ADMIN DISPATCHER
# =========================
async def admin_cmd_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Hanya owner")
        return
    
    if not context.args:
        await admin_cmd(update, context)
        return
    
    cmd = context.args[0].lower()
    
    if cmd == "add":
        context.args = context.args[1:]
        await admin_add(update, context)
    elif cmd == "del":
        context.args = context.args[1:]
        await admin_del(update, context)
    elif cmd == "list":
        await admin_list(update, context)
    else:
        await admin_cmd(update, context)

def setup(app):
    app.add_handler(CommandHandler("admin", admin_cmd_dispatcher))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    
    # Ban management
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    
    # Feature & Limit
    app.add_handler(CommandHandler("feature", toggle_feature))
    app.add_handler(CommandHandler("limit", set_limit))
    app.add_handler(CommandHandler("reset", reset_limit))
    
    # Maintenance
    app.add_handler(CommandHandler("maintenance", maintenance_cmd))

