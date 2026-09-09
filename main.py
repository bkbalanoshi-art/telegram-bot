import asyncio
import glob
import os
import shutil
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import static_ffmpeg
import yt_dlp
from pyrogram import Client, idle


# =========================================================
# FFMPEG
# =========================================================

static_ffmpeg.add_paths()


# =========================================================
# Railway Environment Variables
# =========================================================

API_ID_RAW = os.environ.get("API_ID", "").strip()
API_HASH = os.environ.get("API_HASH", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

if not API_ID_RAW:
    raise RuntimeError("API_ID is missing in Railway Variables")

try:
    API_ID = int(API_ID_RAW)
except ValueError:
    raise RuntimeError("API_ID must be a number")

if not API_HASH:
    raise RuntimeError("API_HASH is missing in Railway Variables")

if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING is missing in Railway Variables")


# =========================================================
# Telegram Client
# =========================================================

app = Client(
    "khan_self",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# =========================================================
# Settings
# =========================================================

IRAN_TZ = ZoneInfo("Asia/Tehran")

DEFAULT_NAME = "𝗞𝗛𝗔𝗡"
TIME_NAME_ACTIVE = False

ME_ID = None

# chat_id -> results
pending_music_choices = {}

PERSIAN_TO_ENG = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789"
)

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

MUSIC_PREFIXES = (
    "اهنگ ",
    "آهنگ ",
    "موزیک ",
    "ترانه ",
    "ریمیکس ",
    "رمیکس ",
    "دانلود اهنگ ",
    "دانلود آهنگ ",
    "دانلود موزیک ",
    "دانلود ترانه ",
    "دانلود ریمیکس ",
    "اهنگ جدید ",
    "آهنگ جدید ",
    "صوتی ",
)


# =========================================================
# Helpers
# =========================================================

def to_bold_time(value: str):
    return "".join(BOLD_DIGITS.get(c, c) for c in value)


def cleanup_file(path):
    if not path:
        return

    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception as e:
        print(
            f"[CLEANUP ERROR] {type(e).__name__}: {e}",
            flush=True
        )


async def safe_edit(client, message, text):
    """
    اول سعی می‌کند پیام خود کاربر را Edit کند.
    اگر نشد، پیام جدید می‌فرستد.
    """

    try:
        await message.edit_text(
            text,
            disable_web_page_preview=True
        )
        return True

    except Exception as edit_error:
        print(
            f"[EDIT ERROR] "
            f"{type(edit_error).__name__}: {edit_error}",
            flush=True
        )

    try:
        await client.send_message(
            message.chat.id,
            text,
            disable_web_page_preview=True
        )

        try:
            await message.delete()
        except Exception:
            pass

        return True

    except Exception as send_error:
        print(
            f"[SEND ERROR] "
            f"{type(send_error).__name__}: {send_error}",
            flush=True
        )

        return False


# =========================================================
# YouTube Search
# =========================================================

def search_music_ultra(query: str, max_results=10):
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "geo_bypass": True,

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        },
    }

    results = []
    seen = set()

    # اول سرچ معمولی یوتیوب
    search_queries = [
        f"ytsearch{max_results}:{query}",
        f"ytmusicsearch{max_results}:{query}",
    ]

    for search_query in search_queries:

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    search_query,
                    download=False
                )

            if not info:
                continue

            entries = info.get("entries") or []

            for entry in entries:

                if not entry:
                    continue

                video_id = entry.get("id")

                url = (
                    entry.get("webpage_url")
                    or entry.get("url")
                )

                # extract_flat بعضی مواقع فقط ID می‌دهد
                if video_id and (
                    not url
                    or not str(url).startswith("http")
                ):
                    url = (
                        "https://www.youtube.com/watch?v="
                        + video_id
                    )

                if not url:
                    continue

                if url in seen:
                    continue

                seen.add(url)

                try:
                    duration = int(
                        entry.get("duration") or 0
                    )
                except Exception:
                    duration = 0

                results.append({
                    "title": entry.get("title") or "Music",

                    "url": url,

                    "duration": duration,

                    "uploader": (
                        entry.get("uploader")
                        or entry.get("channel")
                        or "Artist"
                    ),
                })

                if len(results) >= max_results:
                    break

        except Exception as e:
            print(
                f"[SEARCH ERROR] "
                f"{type(e).__name__}: {e}",
                flush=True
            )

        if len(results) >= max_results:
            break

    return results[:max_results]


# =========================================================
# YouTube Downloader
# =========================================================

def run_yt_download(url: str, is_audio: bool):

    os.makedirs("downloads", exist_ok=True)

    # اسم تصادفی/ID محور باعث می‌شود دانلودهای همزمان
    # روی فایل یکدیگر نوشته نشوند.
    outtmpl = os.path.join(
        "downloads",
        "%(id)s_%(title).45s.%(ext)s"
    )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "outtmpl": outtmpl,

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        },
    }

    if is_audio:

        ydl_opts.update({
            "format": "bestaudio/best",

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        })

    else:

        # این حالت شانس گرفتن فایل قابل ارسال به Telegram
        # را بیشتر می‌کند.
        ydl_opts.update({
            "format": (
                "best[ext=mp4]/"
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "best"
            ),

            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        original_filename = ydl.prepare_filename(info)

    title = info.get("title") or "Media"

    if is_audio:

        base = os.path.splitext(original_filename)[0]

        mp3_path = base + ".mp3"

        if os.path.exists(mp3_path):
            return mp3_path, title

        # fallback
        files = glob.glob(
            glob.escape(base) + ".*"
        )

        for file in files:
            if file.lower().endswith(".mp3"):
                return file, title

        raise FileNotFoundError(
            "FFmpeg finished but MP3 file was not found"
        )

    else:

        # yt-dlp ممکن است بعد از merge نام فایل را تغییر دهد.
        base = os.path.splitext(original_filename)[0]

        candidates = [
            base + ".mp4",
            original_filename,
        ]

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate, title

        files = glob.glob(
            glob.escape(base) + ".*"
        )

        if files:
            return files[0], title

        raise FileNotFoundError(
            "Downloaded video file was not found"
        )


# =========================================================
# Main Message Handler
# =========================================================

@app.on_message()
async def main_handler(client, message):

    global TIME_NAME_ACTIVE
    global ME_ID

    try:

        # ---------------------------------------------
        # فقط پیام‌های خود صاحب اکانت
        # ---------------------------------------------

        if ME_ID is None:
            me = await client.get_me()
            ME_ID = me.id

        if not message.from_user:
            return

        if message.from_user.id != ME_ID:
            return

        # forwarded
        if message.forward_date:
            return

        if not message.text:
            return

        text = message.text.strip()

        if not text:
            return

        lower_text = text.lower()

        chat_id = message.chat.id

        clean_text = text.translate(
            PERSIAN_TO_ENG
        )

        print(
            f"[COMMAND] chat={chat_id} text={text!r}",
            flush=True
        )


        # =================================================
        # انتخاب آهنگ با عدد
        # =================================================

        if (
            clean_text.isdigit()
            and message.reply_to_message
            and chat_id in pending_music_choices
        ):

            idx = int(clean_text) - 1

            result_list = pending_music_choices[
                chat_id
            ]

            if not (0 <= idx < len(result_list)):

                await safe_edit(
                    client,
                    message,
                    "❌ عدد انتخابی داخل لیست نیست."
                )

                return

            selected = result_list[idx]

            # بعد از انتخاب پاک شود
            pending_music_choices.pop(
                chat_id,
                None
            )

            await safe_edit(
                client,
                message,
                "⏳ در حال دانلود آهنگ..."
            )

            path = None

            try:

                path, title = await asyncio.to_thread(
                    run_yt_download,
                    selected["url"],
                    True
                )

                await safe_edit(
                    client,
                    message,
                    "📤 در حال آپلود آهنگ..."
                )

                await client.send_audio(
                    chat_id=chat_id,
                    audio=path,
                    caption=f"🎵 {title}"
                )

                try:
                    await message.delete()
                except Exception:
                    pass

            except Exception as e:

                print(
                    f"[AUDIO ERROR] "
                    f"{type(e).__name__}: {e}",
                    flush=True
                )

                await safe_edit(
                    client,
                    message,
                    "❌ خطا در دانلود آهنگ:\n"
                    + str(e)[:300]
                )

            finally:

                cleanup_file(path)

            return


        # =================================================
        # جستجوی آهنگ
        # =================================================

        matched_prefix = next(
            (
                prefix
                for prefix in MUSIC_PREFIXES
                if lower_text.startswith(prefix)
            ),
            None
        )

        if matched_prefix:

            query = text[
                len(matched_prefix):
            ].strip()

            if not query:

                await safe_edit(
                    client,
                    message,
                    "❌ نام آهنگ یا خواننده را وارد کنید."
                )

                return

            await safe_edit(
                client,
                message,
                f"🔍 در حال جستجو برای: {query}"
            )

            results = await asyncio.to_thread(
                search_music_ultra,
                query,
                10
            )

            if not results:

                await safe_edit(
                    client,
                    message,
                    "❌ نتیجه‌ای پیدا نشد."
                )

                return

            pending_music_choices[
                chat_id
            ] = results

            lines = [
                f"🎧 نتایج برای: {query}",
                ""
            ]

            for i, result in enumerate(
                results,
                start=1
            ):

                duration = result[
                    "duration"
                ]

                if duration:

                    dur = (
                        f"{duration // 60}:"
                        f"{duration % 60:02d}"
                    )

                else:

                    dur = "??:??"

                title = result[
                    "title"
                ].replace("\n", " ")

                lines.append(
                    f"{i}. {title[:45]} | {dur}"
                )

            lines.extend([
                "",
                "روی همین پیام ریپلای کنید و "
                "عدد آهنگ را بفرستید؛ مثلاً 1 یا 10."
            ])

            await safe_edit(
                client,
                message,
                "\n".join(lines)
            )

            return


        # =================================================
        # دانلود ویدیو
        # =================================================

        if (
            lower_text.startswith("ویدیو ")
            or lower_text.startswith("کلیپ ")
        ):

            parts = text.split(
                maxsplit=1
            )

            if len(parts) < 2:

                await safe_edit(
                    client,
                    message,
                    "❌ نام ویدیو را وارد کنید."
                )

                return

            query = parts[1].strip()

            if not query:
                return

            await safe_edit(
                client,
                message,
                f"🔍 در حال جستجوی ویدیو: {query}"
            )

            results = await asyncio.to_thread(
                search_music_ultra,
                query,
                1
            )

            if not results:

                await safe_edit(
                    client,
                    message,
                    "❌ ویدیویی پیدا نشد."
                )

                return

            path = None

            try:

                await safe_edit(
                    client,
                    message,
                    "⏳ در حال دانلود ویدیو..."
                )

                path, title = await asyncio.to_thread(
                    run_yt_download,
                    results[0]["url"],
                    False
                )

                await safe_edit(
                    client,
                    message,
                    "📤 در حال آپلود ویدیو..."
                )

                await client.send_video(
                    chat_id=chat_id,
                    video=path,
                    caption=f"🎬 {title}",
                    supports_streaming=True
                )

                try:
                    await message.delete()
                except Exception:
                    pass

            except Exception as e:

                print(
                    f"[VIDEO ERROR] "
                    f"{type(e).__name__}: {e}",
                    flush=True
                )

                await safe_edit(
                    client,
                    message,
                    "❌ خطای دانلود ویدیو:\n"
                    + str(e)[:300]
                )

            finally:

                cleanup_file(path)

            return


        # =================================================
        # Panel
        # =================================================

        if lower_text in {
            "پنل",
            "منو",
            "panel",
            ".panel",
            "/panel"
        }:

            panel = (
                "╭───「 👑 KHAN SELF 」\n"
                "│\n"
                "├ 🎵 اهنگ <نام>\n"
                "│   جستجوی ۱۰ آهنگ\n"
                "│\n"
                "├ 🎬 ویدیو <نام>\n"
                "│   دانلود ویدیو\n"
                "│\n"
                "├ ⏱ ساعت\n"
                "│   ساعت ایران\n"
                "│\n"
                "├ 👤 تایم فعال\n"
                "├ 👤 تایم خاموش\n"
                "│\n"
                "├ 🚀 پینگ\n"
                "│\n"
                "╰───「 ⚡ Online 」"
            )

            await safe_edit(
                client,
                message,
                panel
            )

            return


        # =================================================
        # Time
        # =================================================

        if lower_text in {
            "ساعت",
            "time",
            ".time",
            "/time"
        }:

            now = datetime.now(
                IRAN_TZ
            ).strftime(
                "%H:%M:%S"
            )

            await safe_edit(
                client,
                message,
                f"⏰ ساعت ایران: {now}"
            )

            return


        # =================================================
        # Ping
        # =================================================

        if lower_text in {
            "پینگ",
            "ping",
            ".ping",
            "/ping"
        }:

            await safe_edit(
                client,
                message,
                "🚀 سلف‌بات فعال و آنلاین است!"
            )

            return


        # =================================================
        # Time Name ON
        # =================================================

        if lower_text == "تایم فعال":

            TIME_NAME_ACTIVE = True

            await safe_edit(
                client,
                message,
                "✅ اسم ساعتی فعال شد."
            )

            return


        # =================================================
        # Time Name OFF
        # =================================================

        if lower_text == "تایم خاموش":

            TIME_NAME_ACTIVE = False

            try:

                await client.update_profile(
                    first_name=DEFAULT_NAME
                )

            except Exception as e:

                print(
                    f"[PROFILE ERROR] "
                    f"{type(e).__name__}: {e}",
                    flush=True
                )

            await safe_edit(
                client,
                message,
                "❌ اسم ساعتی خاموش شد."
            )

            return


    except Exception:

        print(
            "[HANDLER CRASH]\n"
            + traceback.format_exc(),
            flush=True
        )


# =========================================================
# Clock Profile Task
# =========================================================

async def time_task():

    last_value = None

    while True:

        try:

            if TIME_NAME_ACTIVE:

                now = datetime.now(
                    IRAN_TZ
                ).strftime(
                    "%H:%M"
                )

                bold = to_bold_time(now)

                profile_name = (
                    f"{DEFAULT_NAME} ┃ {bold}"
                )

                # اگر دقیقه عوض نشده دوباره API Call نزن
                if profile_name != last_value:

                    await app.update_profile(
                        first_name=profile_name
                    )

                    last_value = profile_name

                    print(
                        f"[TIME NAME] {profile_name}",
                        flush=True
                    )

            else:

                last_value = None

        except Exception as e:

            print(
                f"[TIME TASK ERROR] "
                f"{type(e).__name__}: {e}",
                flush=True
            )

        await asyncio.sleep(30)


# =========================================================
# Start
# =========================================================

async def main():

    global ME_ID

    print(
        ">>> Starting KHAN SELF...",
        flush=True
    )

    try:

        await app.start()

        me = await app.get_me()

        ME_ID = me.id

        print(
            "======================================",
            flush=True
        )

        print(
            f">>> LOGIN OK | ID={me.id} "
            f"| USERNAME={me.username}",
            flush=True
        )

        print(
            ">>> KHAN SELF IS ONLINE AND READY",
            flush=True
        )

        print(
            "======================================",
            flush=True
        )

        asyncio.create_task(
            time_task()
        )

        await idle()

    except Exception:

        print(
            "[STARTUP CRASH]\n"
            + traceback.format_exc(),
            flush=True
        )

        raise

    finally:

        try:
            await app.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
