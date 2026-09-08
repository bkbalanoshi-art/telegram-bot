from pyrogram import Client, filters
import os
from datetime import datetime
from zoneinfo import ZoneInfo

api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string
)

# تنظیم منطقه زمانی ایران و آمریکا (نیویورک)
IRAN_TZ = ZoneInfo("Asia/Tehran")
US_TZ = ZoneInfo("America/New_York") 

# دیکشنری برای تبدیل روزهای هفته به فارسی
persian_weekdays = {
    "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه", "Friday": "جمعه"
}

# فقط به پیام های خودت جواب میده
@app.on_message(filters.private & filters.me)
async def handle_commands(client, message):
    if not message.text:
        return

    text = message.text.strip()

    # دستور ساعت
    if text in ["ساعت", "/ساعت", "time"]:
        iran_time = datetime.now(IRAN_TZ).strftime('%H:%M:%S')
        us_time = datetime.now(US_TZ).strftime('%H:%M:%S')
        await message.reply(
            f"🇮🇷 **ساعت ایران:** `{iran_time}`\n"
            f"🇺🇸 **ساعت آمریکا (نیویورک):** `{us_time}`"
        )

    # دستور تاریخ
    elif text in ["تاریخ", "/تاریخ", "date"]:
        iran_date = datetime.now(IRAN_TZ)
        us_date = datetime.now(US_TZ)
        await message.reply(
            f"🇮🇷 **تاریخ ایران:** `{iran_date.strftime('%Y-%m-%d')}`\n"
            f"🇺🇸 **تاریخ آمریکا:** `{us_date.strftime('%Y-%m-%d')}`"
        )

    # دستور روز هفته
    elif text in ["روز", "/روز", "weekday"]:
        iran_day = persian_weekdays.get(datetime.now(IRAN_TZ).strftime("%A"), "")
        us_day = datetime.now(US_TZ).strftime("%A")
        await message.reply(
            f"🇮🇷 **روز در ایران:** {iran_day}\n"
            f"🇺🇸 **روز در آمریکا:** {us_day}"
        )


if __name__ == "__main__":
    print("سلف‌بات فعال شد...")
    app.run()
