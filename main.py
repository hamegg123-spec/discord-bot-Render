# main.py ver27.1 (Render完全統合版)
import os
import asyncio
import datetime
import traceback
import discord

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [DiscordBot] {msg}", flush=True)

log("=== Discord Bot モジュール読み込み ===")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)
bot_ready = False
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    log(f"🟢 Discord Bot ログイン成功: {bot.user}")
    log("所属Guild一覧: " + ", ".join([g.name for g in bot.guilds]))
    
    bot.loop.create_task(send_worker())
    log("▶️ Discord 投稿ワーカー（キュー監視ループ）を開始しました")

async def send_worker():
    log("[WORKER] 📥 キュー監視ループが正常に起動しました。")
    while True:
        try:
            channel_id, text = await send_queue.get()
            log(f"[WORKER] キューからデータを検知。送信処理を開始します... (対象チャンネル: {channel_id})")
            
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                log(f"[WORKER] ⚠️ チャンネルID {channel_id} の取得を試みます...")
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except Exception as fetch_err:
                    log(f"[WORKER] ❌ チャンネル取得失敗: {fetch_err}")
                    continue

            await channel.send(text)
            log(f"[WORKER] ✅ Discordへのメッセージ投稿が完了しました！")
            
        except Exception as e:
            log(f"[WORKER] ❌ 送信エラー:\n{traceback.format_exc()}")
        finally:
            await asyncio.sleep(0.5)
            try:
                send_queue.task_done()
            except:
                pass

def enqueue_message(channel_id, text):
    if bot.loop and bot.loop.is_running():
        log(f"[QueueInput] Flaskからメッセージを受信。キューへ追加します。")
        asyncio.run_coroutine_threadsafe(send_queue.put((channel_id, text)), bot.loop)
        return True
    else:
        log("[QueueInput] ❌ エラー: Discordのイベントループが稼働していません。")
        return False
