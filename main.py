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

# Bot 準備フラグ
bot_ready = False

# 投稿キュー (asyncioの標準キュー)
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    log(f"🟢 Discord Bot ログイン成功: {bot.user}")
    log("所属Guild一覧: " + ", ".join([g.name for g in bot.guilds]))
    
    # 確実にBotと同じループでワーカーを動かす
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
                log(f"[WORKER] ⚠️ チャンネルID {channel_id} がBotから見つかりません。キャッシュにないため取得を試みます...")
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except Exception as fetch_err:
                    log(f"[WORKER] ❌ チャンネルの取得に完全に失敗しました。IDが正しいか、Botがサーバーにいるか確認してください: {fetch_err}")
                    continue

            await channel.send(text)
            log(f"[WORKER] ✅ Discordへのメッセージ投稿が完了しました！")
            
        except Exception as e:
            log(f"[WORKER] ❌ 送信処理中に致命的なエラーが発生しました:\n{traceback.format_exc()}")
        finally:
            await asyncio.sleep(0.5)
            try:
                send_queue.task_done()
            except:
                pass

def enqueue_message(channel_id, text):
    """Flask(別スレッド)から安全にDiscordのイベントループのキューへデータを追加する"""
    if bot.loop and bot.loop.is_running():
        log(f"[QueueInput] Flaskからメッセージを受信。Discordのループへタスクを安全に委託します。")
        asyncio.run_coroutine_threadsafe(send_queue.put((channel_id, text)), bot.loop)
        return True
    else:
        log("[QueueInput] ❌ エラー: Discordのイベントループがまだ動いていません。")
        return False
