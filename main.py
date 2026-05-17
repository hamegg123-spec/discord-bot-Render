# main.py ver27.1 (Render統合・状態管理外部化・ログレベル制御版)
import os
import asyncio
import datetime
import traceback
import discord

# フラグ管理ファイルをインポート
import state

# 環境変数からログレベルを取得 (デフォルトは INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def log(msg, level="INFO"):
    """指定されたレベルが現在のLOG_LEVELを満たしている場合のみ出力する関数"""
    levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    current_idx = levels.get(LOG_LEVEL, 1)
    msg_idx = levels.get(level.upper(), 0)

    if msg_idx >= current_idx:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [DiscordBot-{level.upper()}] {msg}", flush=True)

log("=== Discord Bot モジュール読み込み ===", "INFO")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    # stateモジュール側のフラグを更新（循環インポートが発生しない）
    state.bot_ready = True
    log(f"🟢 Discord Bot ログイン成功: {bot.user}", "INFO")
    log("所属Guild一覧: " + ", ".join([g.name for g in bot.guilds]), "INFO")
    
    bot.loop.create_task(send_worker())
    log("▶️ Discord 投稿ワーカー（キュー監視ループ）を開始しました", "INFO")

async def send_worker():
    log("[WORKER] 📥 キュー監視ループが正常に起動しました。", "INFO")
    while True:
        try:
            channel_id, text = await send_queue.get()
            log(f"[WORKER] キューからデータを検知。送信処理を開始します... (対象チャンネル: {channel_id})", "DEBUG")
            
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                log(f"[WORKER] ⚠️ チャンネルID {channel_id} の取得を試みます...", "WARNING")
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except Exception as fetch_err:
                    log(f"[WORKER] ❌ チャンネル取得失敗: {fetch_err}", "ERROR")
                    continue

            await channel.send(text)
            log(f"[WORKER] ✅ Discordへのメッセージ投稿が完了しました！", "INFO")
            
        except Exception as e:
            log(f"[WORKER] ❌ 送信エラー:\n{traceback.format_exc()}", "ERROR")
        finally:
            await asyncio.sleep(0.5)
            try:
                send_queue.task_done()
            except:
                pass

def enqueue_message(channel_id, text):
    if bot.loop and bot.loop.is_running():
        log(f"[QueueInput] Flaskからメッセージを受信。キューへ追加します。", "DEBUG")
        asyncio.run_coroutine_threadsafe(send_queue.put((channel_id, text)), bot.loop)
        return True
    else:
        log("[QueueInput] ❌ エラー: Discordのイベントループが稼働していません。", "ERROR")
        return False
