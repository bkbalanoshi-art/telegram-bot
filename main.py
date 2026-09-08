from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
from datetime import datetime, timedelta, timezone

api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string
)

MY_USER_ID = 8989331210  # آیدی تو
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def get_iran_time():
    return datetime.now(IRAN_TZ)


def get_main_panel():
    keyboard = [
        [KeyboardButton("⏰ ساعت ایران"), KeyboardButton("📅 تاریخ ایران")],
        [KeyboardButton("📊 روز هفته"), KeyboardButton("❌ بستن")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


@app.on_message(filters.private & filters.me)
async def handle_message(client, message):
    if not message.from_user or message.from_user.id != MY_USER_ID:
        return
    if not message.text:
        return

    text = message.text.strip()

    if text in ["پنل", "panel", "منو", "menu", "/panel"]:
        await message.reply(
            "╔════════════════════════╗\n"
            "║  🎛️ پنل مدیریت ربات  ║\n"
            "╚════════════════════════╝\n\n"
            "یکی از گزینه‌های کیبورد رو بزن:",
            reply_markup=get_main_panel()
        )

    elif text == "⏰ ساعت ایران":
        now = get_iran_time()
        await message.reply(f"⏰ ساعت ایران: `{now.strftime('%H:%M:%S')}`")

    elif text == "📅 تاریخ ایران":
        now = get_iran_time()
        months = ["", "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
                  "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]
        await message.reply(
            f"📅 تاریخ: `{now.strftime('%Y-%m-%d')}`\n"
            f"ماه: {months[now.month]}\n"
            f"سال: {now.year}"
        )

    elif text == "📊 روز هفته":
        now = get_iran_time()
        weekdays = {
            "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
            "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
            "Thursday": "پنج‌شنبه", "Friday": "جمعه"
        }
        await message.reply(f"📊 امروز: {weekdays.get(now.strftime('%A'), '')}")

    elif text == "❌ بستن":
        await message.reply("پنل بسته شد!", reply_markup=ReplyKeyboardRemove())


if __name__ == "__main__":
    print("ربات در حال استارت شدن...")
    app.run()
