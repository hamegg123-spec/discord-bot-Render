# main.py ver27.1 (Render完全統合版)

import os
import asyncio
import datetime
import discord

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [Discord] {msg}")

log("=== Discord Bot モジュール読み込み ===")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

# Bot 準備フラグ
bot_ready = False

# 投稿キュー (asyncioの標準キュー)
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    log(f"🟢 Discord Bot ログイン成功: {bot.user}")
    log("Guild一覧: " + ", ".join([g.name for g in bot.guilds]))
    
    # 確実にBotと同じループでワーカーを動かす
    bot.loop.create_task(send_worker())
    log("▶️ Discord 投稿ワーカー開始")

async def send_worker():
    log("[WORKER] 監視ループが起動しました。")
    while True:
        try:
            channel, text = await send_queue.get()
            log(f"[WORKER] 📥 キューからデータを検知！ 送信開始 → チャンネル: {channel.id}")
            
            await channel.send(text)
            log(f"[WORKER] ✅ Discordへの投稿が完了しました！")
            
        except Exception as e:
            log(f"[WORKER] ❌ 送信エラー: {e}")
        finally:
            await asyncio.sleep(1)
            try:
                send_queue.task_done()
            except:
                pass
