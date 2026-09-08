from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import os
import asyncio
import random
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

# 👇 اینجا User ID خودت رو بذار
MY_USER_ID = 123456789

# فونت‌های تیره و سنگین
HEAVY_FONTS = [
    "𝐤𝐡𝐚𝐧",
    "𝗸𝗵𝗮𝗻",
    "𝙠𝙝𝙖𝙣",
    "ⓀⒽⒶⓃ",
    "🅺🅷🅰🅽",
    "🄺🄷🄰🄽",
    "ᵏʰᵃⁿ",
    "ᴷᴴᴬᴺ",
]

# تگ‌ها
TAGS = [
    "khan", "Khan", "KHAN", "خان", "خانم",
    "Mr.Khan", "K H A N", "★khan★", "『khan』",
    "khan.", "khan,", "khan:", "khan -", "khan |",
    "✦khan", "khan✦", "►khan", "khan◄",
]

# قالب‌های پیام
TIME_TEMPLATES = [
    "{tag} ⏰ {time}",
    "{tag} | {time}",
    "{tag} ─ {time}",
    "{tag} :: {time}",
    "┏ {tag}\n┗ {time}",
    "▸ {tag}\n▸ {time}",
    "{tag} ➤ {time}",
    "{tag} ✦ {time}",
    "»» {tag} ««\n  {time}",
    "{tag}\n⏱ {time}",
    "⏰ {time} | {tag}",
    "{time} ━━ {tag}",
    "● {tag} • {time}",
    "❰{time}❱ {tag}",
    "{tag} ⟶ {time}",
    "◤ {tag} ◢ {time}",
    "╠═ {tag} ═╣ {time}",
    "♛ {tag} ♛\n⏰ {time}",
    "{tag} ━━━━━━━━━━━━━━━━━\n        {time}",
    "▰▰▰ {tag} ▰▰▰\n          {time}",
]

# روزهای هفته فارسی
PERSIAN_WEEKDAYS = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه",
    "Friday": "جمعه",
}

# ماه‌های فارسی
PERSIAN_MONTHS = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد",
    4: "تیر", 5: "مرداد", 6: "شهریور",
    7: "مهر", 8: "آبان", 9: "آذر",
    10: "دی", 11: "بهمن", 12: "اسفند",
}

# مناطق زمانی
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
US_EASTERN = timezone(timedelta(hours=-5))  # EST
US_PACIFIC = timezone(timedelta(hours=-8))  # PST

last_sent_hour = -1
last_sent_minute = -1


def get_iran_time():
    return datetime.now(IRAN_TZ)


def get_us_eastern():
    return datetime.now(US_EASTERN)


def get_us_pacific():
    return datetime.now(US_PACIFIC)


def get_random_style():
    tag = random.choice(TAGS)
    template = random.choice(TIME_TEMPLATES)
    return tag, template


def to_persian_date(dt):
    """تبدیل تاریخ میلادی به شمسی (ساده)"""
    gy = dt.year
    gm = dt.month
    gd = dt.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gm <= 2:
        gy2 = gy - 1
    else:
        gy2 = gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = (days + 1) // 31 if days < 186 else 6 + (days + 1) // 30
    jd = 1 + ((days + 1) % 31) if days < 186 else 1 + ((days + 1) % 30)
    return jy, jm, jd


def get_persian_date_text():
    now = get_iran_time()
    jy, jm, jd = to_persian_date(now)
    month_name = PERSIAN_MONTHS.get(jm, "")
    weekday = PERSIAN_WEEKDAYS.get(now.strftime("%A"), "")
    return f"{weekday} {jd} {month_name} {jy}"


# ============== پنل اصلی ==============

def get_main_panel():
    keyboard = [
        [InlineKeyboardButton("⏰ ساعت ایران", callback_data="time_iran")],
        [InlineKeyboardButton("🕐 ساعت آمریکا شرقی", callback_data="time_us_east")],
        [InlineKeyboardButton("🕓 ساعت آمریکا غربی", callback_data="time_us_west")],
        [
            InlineKeyboardButton("📅 تاریخ ایران", callback_data="date_iran"),
            InlineKeyboardButton("📅 تاریخ آمریکا", callback_data="date_us"),
        ],
        [InlineKeyboardButton("📊 روز هفته", callback_data="weekday")],
        [InlineKeyboardButton("🔄 رفرش همه", callback_data="refresh_all")],
        [InlineKeyboardButton("❌ بستن پنل", callback_data="close_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ============== حلقه ساعت خودکار ==============

async def send_time_message():
    global last_sent_hour, last_sent_minute
    while True:
        try:
            now = get_iran_time()
            current_time_str = now.strftime("%H:%M:%S")

            if now.hour != last_sent_hour or now.minute != last_sent_minute:
                last_sent_hour = now.hour
                last_sent_minute = now.minute

                tag, template = get_random_style()
                time_msg = template.format(tag=tag, time=current_time_str)

                await app.send_message("me", time_msg)
                print(f"[{current_time_str}] Sent: {time_msg}")

        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(30)


# ============== هندل پیام ==============

@app.on_message(filters.private)
async def handle_message(client, message: Message):
    try:
        if not message.from_user or message.from_user.id != MY_USER_ID:
            return

        if message.from_user.is_self:
            return

        if not message.text:
            return

        text = message.text.strip()

        # باز کردن پنل
        if text in ["پنل", "panel", "/panel", "منو", "menu"]:
            await message.reply(
                "╔════════════════════════╗\n"
                "║  🎛️ پنل مدیریت ربات  ║\n"
                "╚════════════════════════╝\n\n"
                "یکی از گزینه‌ها رو بزن:",
                reply_markup=get_main_panel()
            )

        # دستورات متنی هم کار کنن
        elif "ساعت" in text:
            now = get_iran_time()
            time_str = now.strftime("%H:%M:%S")
            tag, template = get_random_style()
            await message.reply(template.format(tag=tag, time=time_str))

        elif "تاریخ" in text and "ایران" in text:
            await message.reply(f"📅 تاریخ ایران:\n`{get_persian_date_text()}`")

        elif "تاریخ" in text and ("امریکا" in text or "آمریکا" in text):
            us = get_us_eastern()
            await message.reply(f"📅 تاریخ آمریکا (شرقی):\n`{us.strftime('%A %Y-%m-%d')}`")

    except Exception as e:
        print(f"Error: {e}")


# ============== هندل دکمه‌های پنل ==============

@app.on_callback_query()
async def handle_callback(client, callback_query):
    try:
        if callback_query.from_user.id != MY_USER_ID:
            await callback_query.answer("❌ دسترسی نداری", show_alert=True)
            return

        data = callback_query.data
        await callback_query.answer()

        if data == "time_iran":
            now = get_iran_time()
            time_str = now.strftime("%H:%M:%S")
            tag, template = get_random_style()
            text = template.format(tag=tag, time=time_str)
            await callback_query.message.reply(f"⏰ **ساعت ایران:**\n`{text}`")

        elif data == "time_us_east":
            us = get_us_eastern()
            time_str = us.strftime("%H:%M:%S")
            text = f"🕐 ساعت آمریکا شرقی: {time_str}"
            await callback_query.message.reply(f"`{text}`")

        elif data == "time_us_west":
            us = get_us_pacific()
            time_str = us.strftime("%H:%M:%S")
            text = f"🕓 ساعت آمریکا غربی: {time_str}"
            await callback_query.message.reply(f"`{text}`")

        elif data == "date_iran":
            await callback_query.message.reply(
                f"📅 **تاریخ ایران:**\n`{get_persian_date_text()}`"
            )

        elif data == "date_us":
            us = get_us_eastern()
            await callback_query.message.reply(
                f"📅 **تاریخ آمریکا (شرقی):**\n`{us.strftime('%A %Y-%m-%d')}`\n"
                f"📅 **تاریخ آمریکا (غربی):**\n`{get_us_pacific().strftime('%A %Y-%m-%d')}`"
            )

        elif data == "weekday":
            iran = get_iran_time()
            us_e = get_us_eastern()
            us_w = get_us_pacific()
            text = (
                f"📊 **روز هفته:**\n\n"
                f"🇮🇷 ایران: {PERSIAN_WEEKDAYS.get(iran.strftime('%A'), '')}\n"
                f"🇺🇸 آمریکا شرقی: {us_e.strftime('%A')}\n"
                f"🇺🇸 آمریکا غربی: {us_w.strftime('%A')}"
            )
            await callback_query.message.reply(text)

        elif data == "refresh_all":
            iran = get_iran_time()
            us_e = get_us_eastern()
            us_w = get_us_pacific()
            tag, template = get_random_style()
            time_iran = template.format(tag=tag, time=iran.strftime("%H:%M:%S"))

            text = (
                "🔄 **همه اطلاعات:**\n\n"
                f"⏰ ساعت ایران: `{time_iran}`\n"
                f"🕐 ساعت آمریکا شرقی: `{us_e.strftime('%H:%M:%S')}`\n"
                f"🕓 ساعت آمریکا غربی: `{us_w.strftime('%H:%M:%S')}`\n\n"
                f"📅 تاریخ ایران: `{get_persian_date_text()}`\n"
                f"📅 تاریخ آمریکا: `{us_e.strftime('%A %Y-%m-%d')}`\n\n"
                f"📊 روز هفته ایران: {PERSIAN_WEEKDAYS.get(iran.strftime('%A'), '')}"
            )
            await callback_query.message.reply(text, reply_markup=get_main_panel())

        elif data == "close_panel":
            await callback_query.message.delete()
            await callback_query.message.reply("❌ پنل بسته شد")

    except Exception as e:
        print(f"Callback error: {e}")


async def main():
    await app.start()
    me = await app.get_me()
    print("=" * 50)
    print(f"✅ ربات فعال شد")
    print(f"اکانت: {me.first_name}")
    print(f"User ID: {me.id}")
    print("=" * 50)

    asyncio.create_task(send_time_message())
    await asyncio.sleep(99999999)


if __name__ == "__main__":
    app.run(main())
