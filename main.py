import os
from datetime import datetime
from zoneinfo import ZoneInfo
import jdatetime
from pyrogram import Client, filters

api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string,
)

# مناطق زمانی
IRAN_TZ = ZoneInfo("Asia/Tehran")
US_TZ = ZoneInfo("America/New_York")

# دیکشنری روزهای هفته
persian_weekdays = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه",
    "Friday": "جمعه",
}


@app.on_message(filters.me & ~filters.forwarded)
async def handle_commands(client, message):
    if not message.text:
        return

    text = message.text.strip().lower()

    # 1. دستور ساعت
    if text in ["ساعت", "/ساعت", "time", ".time"]:
        iran_time = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        us_time = datetime.now(US_TZ).strftime("%H:%M:%S")

        msg = (
            "⏰ **ساعت رسمی:**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **ایران (تهران):** `{iran_time}`\n"
            f"🇺🇸 **آمریکا (نیویورک):** `{us_time}`"
        )
        await message.edit_text(msg)

    # 2. دستور تاریخ
    elif text in ["تاریخ", "/تاریخ", "date", ".date"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)

        # تاریخ شمسی با حروف و عدد
        j_date = jdatetime.datetime.fromgregorian(datetime=now_iran)
        shamsi_str = j_date.strftime("%Y/%m/%d")
        shamsi_words = f"{j_date.day} {j_date.j_months_fa[j_date.month - 1]}"

        # تاریخ میلادی
        gregorian_str = now_us.strftime("%Y-%m-%d")

        msg = (
            "📅 **تاریخ امروز:**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **شمسی:** `{shamsi_str}` ({shamsi_words})\n"
            f"🇺🇸 **میلادی:** `{gregorian_str}`"
        )
        await message.edit_text(msg)

    # 3. دستور روز هفته
    elif text in ["روز", "/روز", "day", ".day"]:
        iran_day = persian_weekdays.get(
            datetime.now(IRAN_TZ).strftime("%A"), ""
        )
        us_day = datetime.now(US_TZ).strftime("%A")

        msg = (
            "🗓 **امروز چندشنبه است؟**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **ایران:** `{iran_day}`\n"
            f"🇺🇸 **آمریکا:** `{us_day}`"
        )
        await message.edit_text(msg)

    # 4. دستور جامع (همه اطلاعات یکجا)
    elif text in ["زمان", "/زمان", "now", ".now", "info"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)

        iran_time = now_iran.strftime("%H:%M:%S")
        us_time = now_us.strftime("%H:%M:%S")

        j_date = jdatetime.datetime.fromgregorian(datetime=now_iran)
        shamsi_full = f"{j_date.day} {j_date.j_months_fa[j_date.month - 1]} {j_date.year}"
        iran_day = persian_weekdays.get(now_iran.strftime("%A"), "")

        msg = (
            "⏱ **وضعیت کامل زمان و تاریخ:**\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🗓 **امروز:** `{iran_day}`\n"
            f"📅 **تاریخ شمسی:** `{shamsi_full}`\n"
            f"📆 **تاریخ میلادی:** `{now_iran.strftime('%Y/%m/%d')}`\n"
            "─────────────────\n"
            f"🇮🇷 **ساعت ایران:** `{iran_time}`\n"
            f"🇺🇸 **ساعت آمریکا:** `{us_time}`\n"
            "━━━━━━━━━━━━━━━━━"
        )
        await message.edit_text(msg)


if __name__ == "__main__":
    print("سلف‌بات با موفقیت فعال شد...")
    app.run()
