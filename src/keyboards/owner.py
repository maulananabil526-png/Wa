from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import OWNER_USERNAME   # kita pakai config

def kb_owner():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👑 Owner",
                url=f"https://t.me/{OWNER_USERNAME}"
            )
        ]
    ])



