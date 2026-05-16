# main.py ver27.2 (Render Bot 専用 - ログ超強化版)

import os
import threading
import asyncio
import datetime
import discord

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 現在実行されているスレッド名もログに出すことで、原因究極を容易にします
    current_thread = threading.current_thread().name
    print(f"[{now}] [{current_thread}] {msg}")

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
    
    # 確実にBotのイベントループ上でタスクを起動
    bot.loop.create_task(send_worker())
    log("Discord 投稿ワーカー開始（ループ監視をスタートしました）")

async def send_worker():
    log("[SEND_WORKER] ループ監視が正常に起動しました。キューの待機に入ります。")
    while True:
        try:
            log(f"[SEND_WORKER] キューの確認中... 現在のキューサイズ: {send_queue.qsize()}")
            # キューからデータが取り出されるのを待つ
            channel, text = await send_queue.get()
            
            log(f"[SEND_WORKER] 🎉 キューからデータを検知しました！ 送信開始 → チャンネルID: {channel.id}")
            
            # チャンネルの型や権限チェックのログ
            if hasattr(channel, 'name'):
                log(f"[SEND_WORKER] 送信先チャンネル名: #{channel.name} (サーバー: {channel.guild.name})")
            
            await channel.send(text)
            log(f"[SEND_WORKER] ✅ Discordへのメッセージ書き込みが【完了】しました → {channel.id}")
            
        except Exception as e:
            log(f"[SEND_WORKER] ❌ 送信処理中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await asyncio.sleep(1)
            try:
                send_queue.task_done()
                log("[SEND_WORKER] キューのタスク完了マーク(task_done)を設定しました")
            except Exception:
                pass

def start_discord_bot():
    token = os.environ["DISCORD_TOKEN"]
    log("Discord Bot スレッド開始")
    asyncio.run(bot.start(token))

# 明確にスレッド名を付けて起動（ログで判別しやすくするため）
threading.Thread(target=start_discord_bot, name="DiscordBotThread", daemon=True).start()

log("main.py 読み込み完了（Bot 起動中）")
