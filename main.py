# main.py ver27.1 (Render Bot 専用)

import os
import threading
import asyncio
import datetime
import discord

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

log("=== Discord Bot 起動開始 ===")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

# Bot 準備フラグ
bot_ready = False

# 投稿キュー
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    log(f"Discord Bot ログイン成功: {bot.user}")
    log("Guild一覧: " + ", ".join([g.name for g in bot.guilds]))
    bot.loop.create_task(send_worker())
    log("Discord 投稿ワーカー開始")

async def send_worker():
    while True:
        channel, text = await send_queue.get()
        try:
            log(f"[SEND_WORKER] 送信開始 → {channel.id}")
            await channel.send(text)
            log(f"[SEND_WORKER] 送信完了 → {channel.id}")
        except Exception as e:
            log(f"[SEND_WORKER] 送信エラー: {e}")
        finally:
            await asyncio.sleep(1)
            send_queue.task_done()

def start_discord_bot():
    token = os.environ["DISCORD_TOKEN"]
    log("Discord Bot スレッド開始")
    asyncio.run(bot.start(token))

threading.Thread(target=start_discord_bot, daemon=True).start()

log("main.py 読み込み完了（Bot 起動中）")
