import asyncio
import os
from pyrogram import Client, filters, idle

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

app = Client(
    "khan_test",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)


@app.on_message(filters.all)
async def debug_handler(client, message):
    print(
        f"UPDATE RECEIVED | "
        f"chat={getattr(message.chat, 'id', None)} | "
        f"from={getattr(message.from_user, 'id', None)} | "
        f"outgoing={message.outgoing} | "
        f"text={message.text!r}",
        flush=True
    )

    if message.text and message.text.strip() == "پنل":
        try:
            await message.edit_text("✅ پنل کار می‌کند")
            print("PANEL OK", flush=True)
        except Exception as e:
            print(
                f"EDIT ERROR: {type(e).__name__}: {e}",
                flush=True
            )


async def main():
    print("STARTING...", flush=True)

    await app.start()

    me = await app.get_me()

    print(
        f"LOGIN OK | ID={me.id} | @{me.username}",
        flush=True
    )

    print("SEND 'پنل' NOW", flush=True)

    await idle()


if __name__ == "__main__":
    asyncio.run(main())
