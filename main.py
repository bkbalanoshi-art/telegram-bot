import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters

api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

app = Client(
    name="my_account",
    api_id=api_id,
    api_hash=api_hash,
    session_string=session_string
)

# مناطق زمانی
IRAN_TZ = ZoneInfo("Asia/Tehran")
US_TZ = ZoneInfo("America/New_York")

# لیست ماه‌ها و روزهای فارسی
PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

PERSIAN_WEEKDAYS = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه",
    "Friday": "جمعه"
}

# تابع تبدیل تاریخ میلادی به شمسی بدون نیاز به کتابخونه اضافی
def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


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

        jy, jm, jd = gregorian_to_jalali(now_iran.year, now_iran.month, now_iran.day)
        shamsi_str = f"{jy}/{jm:02d}/{jd:02d}"
        month_name = PERSIAN_MONTHS[jm - 1]
        gregorian_str = now_us.strftime("%Y-%m-%d")

        msg = (
            "📅 **تاریخ امروز:**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **شمسی:** `{shamsi_str}` ({jd} {month_name})\n"
            f"🇺🇸 **میلادی:** `{gregorian_str}`"
        )
        await message.edit_text(msg)

    # 3. دستور روز هفته
    elif text in ["روز", "/روز", "day", ".day"]:
        iran_day = PERSIAN_WEEKDAYS.get(datetime.now(IRAN_TZ).strftime("%A"), "")
        us_day = datetime.now(US_TZ).strftime("%A")

        msg = (
            "🗓 **امروز چندشنبه است؟**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **ایران:** `{iran_day}`\n"
            f"🇺🇸 **آمریکا:** `{us_day}`"
        )
        await message.edit_text(msg)

    # 4. دستور جامع (همه چیز یکجا)
    elif text in ["زمان", "/زمان", "now", ".now", "info"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)

        iran_time = now_iran.strftime("%H:%M:%S")
        us_time = now_us.strftime("%H:%M:%S")

        jy, jm, jd = gregorian_to_jalali(now_iran.year, now_iran.month, now_iran.day)
        month_name = PERSIAN_MONTHS[jm - 1]
        shamsi_full = f"{jd} {month_name} {jy}"
        iran_day = PERSIAN_WEEKDAYS.get(now_iran.strftime("%A"), "")

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
