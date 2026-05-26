import json
import os
import asyncio
import requests

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ===== CONFIG =====
BOT_TOKEN = "TOKEN_BOT"
ADMIN_ID = 123456789

DATA_FILE = "targets.json"

# ===== LOAD DATA =====
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

with open(DATA_FILE, "r") as f:
    targets = json.load(f)

status_cache = {}

# ===== SAVE =====
def save():
    with open(DATA_FILE, "w") as f:
        json.dump(targets, f, indent=2)

# ===== CHECK FB =====
def check_facebook(url):
    try:
        r = requests.get(url, timeout=15)

        text = r.text.lower()

        if (
            "content isn't available" in text
            or "trang này hiện không khả dụng" in text
            or r.status_code == 404
        ):
            return "DIE"

        return "LIVE"

    except:
        return "ERROR"

# ===== COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = """
😈 META LIVE BOT

/add <link>
/remove <link>
/list
"""
    await update.message.reply_text(msg)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Dùng: /add <link>")
        return

    url = context.args[0]

    if url in targets:
        await update.message.reply_text("Đã tồn tại.")
        return

    targets.append(url)
    save()

    await update.message.reply_text(f"✅ Đã thêm:\\n{url}")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return

    url = context.args[0]

    if url in targets:
        targets.remove(url)
        save()

        await update.message.reply_text("🗑 Đã xoá")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not targets:
        await update.message.reply_text("Không có mục nào.")
        return

    text = "📋 DANH SÁCH:\\n\\n"

    for x in targets:
        text += f"{x}\\n"

    await update.message.reply_text(text)

# ===== AUTO CHECK =====
async def checker(app):
    while True:
        for url in targets:

            status = check_facebook(url)

            old = status_cache.get(url)

            if old != status:

                status_cache[url] = status

                if status == "DIE":
                    msg = f"💀 ACC DIE:\\n{url}"

                elif status == "LIVE":
                    msg = f"✅ ACC LIVE:\\n{url}"

                else:
                    msg = f"⚠️ ERROR:\\n{url}"

                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=msg
                )

        await asyncio.sleep(300)

# ===== MAIN =====
if __name__ == "__main__":

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("list", list_cmd))

    loop = asyncio.get_event_loop()
    loop.create_task(checker(app))

    print("BOT ONLINE 😈")

    app.run_polling()
