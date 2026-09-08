import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait

# متغیرهای محیطی که از Railway دریافت می‌شوند
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

# تنظیمات اسم ساعتی
DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

# تبدیل اعداد به فونت درشت و توپر
BOLD_DIGITS = {
    "0": "𝟎",
    "1": "𝟏",
    "2": "𝟐",
    "3": "𝟑",
    "4": "𝟒",
    "5": "𝟓",
    "6": "𝟔",
    "7": "𝟕",
    "8": "𝟖",
    "9": "𝟗",
    ":": ":",
}


def to_bold_time(time_str: str) -> str:
    return "".join(BOLD_DIGITS.get(ch, ch) for ch in time_str)


# لیست ماه‌ها و روزهای فارسی
PERSIAN_MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

PERSIAN_WEEKDAYS = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه",
    "Friday": "جمعه",
}


# تابع تبدیل تاریخ میلادی به شمسی بدون نیاز به کتابخانه اضافی
def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
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


# تسک پس‌زمینه برای اسم ساعتی
async def auto_time_name_task():
    global TIME_NAME_ACTIVE
    last_set_time = ""
    while True:
        if TIME_NAME_ACTIVE:
            try:
                current_time = datetime.now(IRAN_TZ).strftime("%H:%M")
                if current_time != last_set_time:
                    bold_time = to_bold_time(current_time)
                    new_name = f"{DEFAULT_NAME} ┃ {bold_time}"
                    await app.update_profile(first_name=new_name)
                    last_set_time = current_time
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Time Name Error: {e}")
        await asyncio.sleep(15)  # هر ۱۵ ثانیه بررسی می‌کند


# دریافت دستورات
@app.on_message(filters.me & ~filters.forwarded)
async def handle_commands(client, message):
    global TIME_NAME_ACTIVE
    if not message.text:
        return

    text = message.text.strip()
    lower_text = text.lower()

    # 1. دستور پنل راهنما
    if lower_text in ["پنل", "منو", "panel", ".panel"]:
        panel_msg = (
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙 𝗣𝗔𝗡𝗘𝗟** 」\n"
            "│\n"
            "├ ⏱ **بخش زمان و تاریخ:**\n"
            "│ • `ساعت` ➔ نمایش ساعت ایران و آمریکا\n"
            "│ • `تاریخ` ➔ نمایش تاریخ شمسی و میلادی\n"
            "│ • `روز` ➔ نمایش روز هفته\n"
            "│ • `زمان` ➔ نمایش کامل تمام اطلاعات زمان\n"
            "│\n"
            "├ 👤 **بخش اسم ساعتی:**\n"
            "│ • `تایم فعال` ➔ فعال‌سازی (𝗞𝗛𝗔𝗡 ┃ 𝟏𝟒:𝟑𝟎)\n"
            "│ • `تایم خاموش` ➔ خاموش کردن و بازگشت به (𝗞𝗛𝗔𝗡)\n"
            "│\n"
            "╰───「 ⚡️ 𝑆𝑡𝑎𝑡𝑢𝑠: 𝑂𝑛𝑙𝑖𝑛𝑒 」"
        )
        await message.edit_text(panel_msg)

    # 2. فعال‌سازی اسم ساعتی
    elif text in ["تایم فعال", "تایم روشن"]:
        TIME_NAME_ACTIVE = True
        current_time = datetime.now(IRAN_TZ).strftime("%H:%M")
        bold_time = to_bold_time(current_time)
        new_name = f"{DEFAULT_NAME} ┃ {bold_time}"
        await app.update_profile(first_name=new_name)
        await message.edit_text("✅ **اسم ساعتی با موفقیت فعال شد:**\n`" + new_name + "`")

    # 3. خاموش کردن اسم ساعتی
    elif text in ["تایم خاموش", "تایم غیرفعال"]:
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await message.edit_text(
            f"❌ **اسم ساعتی خاموش شد.**\nنام به حالت اولیه برگشت: `{DEFAULT_NAME}`"
        )

    # 4. دستور ساعت
    elif lower_text in ["ساعت", "/ساعت", "time", ".time"]:
        iran_time = datetime.now(IRAN_TZ).strftime("%H:%M:%S")
        us_time = datetime.now(US_TZ).strftime("%H:%M:%S")
        msg = (
            "⏰ **ساعت رسمی:**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **ایران (تهران):** `{iran_time}`\n"
            f"🇺🇸 **آمریکا (نیویورک):** `{us_time}`"
        )
        await message.edit_text(msg)

    # 5. دستور تاریخ
    elif lower_text in ["تاریخ", "/تاریخ", "date", ".date"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)
        jy, jm, jd = gregorian_to_jalali(
            now_iran.year, now_iran.month, now_iran.day
        )
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

    # 6. دستور روز هفته
    elif lower_text in ["روز", "/روز", "day", ".day"]:
        iran_day = PERSIAN_WEEKDAYS.get(
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

    # 7. دستور کامل زمان
    elif lower_text in ["زمان", "/زمان", "now", ".now", "info"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)
        iran_time = now_iran.strftime("%H:%M:%S")
        us_time = now_us.strftime("%H:%M:%S")
        jy, jm, jd = gregorian_to_jalali(
            now_iran.year, now_iran.month, now_iran.day
        )
        shamsi_full = f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}"
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


async def main():
    await app.start()
    asyncio.create_task(auto_time_name_task())
    print("سلف‌بات خان فعال شد و آماده استفاده است...")
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(main())
