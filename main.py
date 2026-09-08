import asyncio
import os
import glob
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
import yt_dlp
import static_ffmpeg

# فعال‌سازی خودکار FFMPEG برای تبدیل آهنگ
static_ffmpeg.add_paths()

# متغیرهای محیطی Railway
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

BOLD_DIGITS = {
    "0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒",
    "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗", ":": ":"
}

def to_bold_time(time_str: str) -> str:
    return "".join(BOLD_DIGITS.get(ch, ch) for ch in time_str)

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

PERSIAN_WEEKDAYS = {
    "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه", "Friday": "جمعه"
}

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


# تابع دانلود و ارسال آهنگ/ویدیو
async def download_and_send(client, message, query, is_audio=False):
    await message.edit_text("⏳ **در حال جستجو و دانلود...**")

    file_path = None
    try:
        os.makedirs("downloads", exist_ok=True)

        # اگر لینک مستقیم بود از خودش استفاده کن، وگرنه در یوتیوب سرچ کن
        if query.startswith(("http://", "https://")):
            url = query
        else:
            search_query = f"ytsearch1:{query}"
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if not info or "entries" not in info or not info["entries"]:
                    await message.edit_text("❌ **هیچ نتیجه‌ای یافت نشد.**")
                    return
                url = info["entries"][0]["webpage_url"]

        # تنظیمات دانلود
        if is_audio:
            ydl_opts = {
                "outtmpl": "downloads/%(title).50s.%(ext)s",
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "no_warnings": True,
            }
        else:
            ydl_opts = {
                "outtmpl": "downloads/%(title).50s.%(ext)s",
                "format": "best[ext=mp4]/best",
                "quiet": True,
                "no_warnings": True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base = os.path.splitext(filename)[0]
            files = glob.glob(f"{glob.escape(base)}.*")
            file_path = files[0] if files else filename

        title = info.get("title", "Music")

        await message.edit_text("📤 **دانلود شد! در حال ارسال...**")

        if is_audio or file_path.endswith(".mp3"):
            await message.reply_audio(
                audio=file_path,
                title=title,
                caption=f"🎵 **{title}**",
            )
        elif file_path.endswith((".mp4", ".mkv", ".mov", ".webm")):
            await message.reply_video(
                video=file_path,
                caption=f"🎬 **{title}**",
            )
        else:
            await message.reply_document(
                document=file_path,
                caption=f"📁 **{title}**",
            )

        # حذف فایل موقت و پیام دستور
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await message.delete()

    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await message.edit_text(f"❌ **خطا:**\n`{str(e)[:200]}`")


# تسک پس‌زمینه اسم ساعتی
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
        await asyncio.sleep(15)


@app.on_message(filters.me & ~filters.forwarded)
async def handle_commands(client, message):
    global TIME_NAME_ACTIVE
    if not message.text:
        return

    text = message.text.strip()
    lower_text = text.lower()

    # ─── ۱. پنل راهنما ───
    if lower_text in ["پنل", "منو", "panel", ".panel"]:
        panel_msg = (
            "╭───「 👑 **𝗞𝗛𝗔𝗡 𝗦𝗘𝗟𝗙 𝗣𝗔𝗡𝗘𝗟** 」\n"
            "│\n"
            "├ 🎵 **بخش دانلود:**\n"
            "│ • `اهنگ شادمهر` ➔ جستجو و دانلود آهنگ\n"
            "│ • `ویدیو کلیپ` ➔ جستجو و دانلود ویدیو\n"
            "│ • `دانلود لینک` ➔ دانلود از لینک مستقیم\n"
            "│\n"
            "├ ⏱ **بخش زمان و تاریخ:**\n"
            "│ • `ساعت` ➔ ساعت ایران و آمریکا\n"
            "│ • `تاریخ` ➔ تاریخ شمسی و میلادی\n"
            "│ • `روز` ➔ نمایش روز هفته\n"
            "│ • `زمان` ➔ وضعیت کامل زمان\n"
            "│\n"
            "├ 👤 **بخش اسم ساعتی:**\n"
            "│ • `تایم فعال` ➔ فعال‌سازی (𝗞𝗛𝗔𝗡 ┃ 𝟏𝟒:𝟑𝟎)\n"
            "│ • `تایم خاموش` ➔ بازگشت به (𝗞𝗛𝗔𝗡)\n"
            "│\n"
            "╰───「 ⚡️ 𝑆𝑡𝑎𝑡𝑢𝑠: 𝑂𝑛𝑙𝑖𝑛𝑒 」"
        )
        await message.edit_text(panel_msg)

    # ─── ۲. دانلود آهنگ با اسم ───
    elif lower_text.startswith("اهنگ ") or lower_text.startswith("آهنگ "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send(client, message, query, is_audio=True)

    # ─── ۳. دانلود ویدیو با اسم ───
    elif lower_text.startswith("ویدیو "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send(client, message, query, is_audio=False)

    # ─── ۴. دانلود از لینک ───
    elif lower_text.startswith("دانلود ") or lower_text.startswith("dl "):
        query = text.split(maxsplit=1)[1].strip()
        await download_and_send(client, message, query, is_audio=False)

    # ─── ۵. فعال‌سازی اسم ساعتی ───
    elif text in ["تایم فعال", "تایم روشن"]:
        TIME_NAME_ACTIVE = True
        current_time = datetime.now(IRAN_TZ).strftime("%H:%M")
        bold_time = to_bold_time(current_time)
        new_name = f"{DEFAULT_NAME} ┃ {bold_time}"
        await app.update_profile(first_name=new_name)
        await message.edit_text(f"✅ **اسم ساعتی فعال شد:**\n`{new_name}`")

    # ─── ۶. خاموش کردن اسم ساعتی ───
    elif text in ["تایم خاموش", "تایم غیرفعال"]:
        TIME_NAME_ACTIVE = False
        await app.update_profile(first_name=DEFAULT_NAME)
        await message.edit_text(
            f"❌ **اسم ساعتی خاموش شد.**\nنام به حالت اولیه برگشت: `{DEFAULT_NAME}`"
        )

    # ─── ۷. ساعت ───
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

    # ─── ۸. تاریخ ───
    elif lower_text in ["تاریخ", "/تاریخ", "date", ".date"]:
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

    # ─── ۹. روز هفته ───
    elif lower_text in ["روز", "/روز", "day", ".day"]:
        iran_day = PERSIAN_WEEKDAYS.get(datetime.now(IRAN_TZ).strftime("%A"), "")
        us_day = datetime.now(US_TZ).strftime("%A")
        msg = (
            "🗓 **امروز چندشنبه است؟**\n"
            "━━━━━━━━━━━━━━\n"
            f"🇮🇷 **ایران:** `{iran_day}`\n"
            f"🇺🇸 **آمریکا:** `{us_day}`"
        )
        await message.edit_text(msg)

    # ─── ۱۰. زمان کامل ───
    elif lower_text in ["زمان", "/زمان", "now", ".now", "info"]:
        now_iran = datetime.now(IRAN_TZ)
        now_us = datetime.now(US_TZ)
        iran_time = now_iran.strftime("%H:%M:%S")
        us_time = now_us.strftime("%H:%M:%S")
        jy, jm, jd = gregorian_to_jalali(now_iran.year, now_iran.month, now_iran.day)
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
    print("سلف‌بات خان با موفقیت فعال شد...")
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(main())
