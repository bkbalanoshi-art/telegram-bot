from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import asyncio
from datetime import datetime, timedelta, timezone

api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]
session_string = os.environ["SESSION_STRING"]

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string
)

MY_USER_ID = 8989331210  # ✅ ایدی تو

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def get_iran_time():
    return datetime.now(IRAN_TZ)


def get_main_panel():
    keyboard = [
        [InlineKeyboardButton("⏰ ساعت ایران", callback_data="time_iran")],
        [InlineKeyboardButton("📅 تاریخ ایران", callback_data="date_iran")],
        [InlineKeyboardButton("📊 روز هفته", callback_data="weekday")],
        [InlineKeyboardButton("❌ بستن", callback_data="close")],
    ]
    return InlineKeyboardMarkup(keyboard)


@app.on_message(filters.private)
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
            "یکی از گزینه‌ها رو بزن:",
            reply_markup=get_main_panel()
        )


@app.on_callback_query()
async def handle_callback(client, callback_query):
    if callback_query.from_user.id != MY_USER_ID:
        await callback_query.answer("❌ دسترسی نداری", show_alert=True)
        return

    data = callback_query.data
    await callback_query.answer()

    if data == "time_iran":
        now = get_iran_time()
        await callback_query.message.reply(
            f"⏰ ساعت ایران: `{now.strftime('%H:%M:%S')}`"
        )

    elif data == "date_iran":
        now = get_iran_time()
        months = ["", "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
                  "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]
        await callback_query.message.reply(
            f"📅 تاریخ: `{now.strftime('%Y-%m-%d')}`\n"
            f"ماه: {months[now.month]}\n"
            f"سال: {now.year}"
        )

    elif data == "weekday":
        now = get_iran_time()
        weekdays = {
            "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
            "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
            "Thursday": "پنج‌شنبه", "Friday": "جمعه"
        }
        await callback_query.message.reply(
            f"📊 امروز: {weekdays.get(now.strftime('%A'), '')}"
        )

    elif data == "close":
        await callback_query.message.delete()


async def main():
    await app.start()
    me = await app.get_me()
    print("=" * 50)
    print(f"✅ ربات فعال شد")
    print(f"اکانت: {me.first_name}")
    print("=" * 50)
    await asyncio.sleep(99999999)


if __name__ == "__main__":
    app.run(main())
