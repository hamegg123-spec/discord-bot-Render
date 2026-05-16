# ============================================================================
# main.py ver27.1 (Render 対応版)
#   - Railway ver26.6 の「投稿キュー＋1秒ディレイ」を Render 用に完全移植
#   - FastAPI → Flask に置き換え（Render は gunicorn + Flask のため）
#   - Discord Bot は別スレッドで起動
#   - app.py から import される構造に最適化
# ----------------------------------------------------------------------------
# 【変更履歴】
# [2026-05-16] senoo / Copilot
# - Railway の main.py ver26.6 を Render 用に移植
# - Flask API（/post, /postCastleEvent）を main.py 内に実装
# - Discord Bot をスレッドで起動し、Flask と共存
# - 投稿キュー（asyncio.Queue）＋1秒ディレイワーカーを完全再現
# ============================================================================

import os
import threading
import asyncio
import datetime
import discord
from discord.ext import commands
from flask import Flask, request, jsonify

# ============================================================================
# ログ関数
# ============================================================================
def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# ============================================================================
# Discord Bot（投稿キュー方式）
# ============================================================================

log("=== Discord Bot 起動開始 ===")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

# ★ 投稿キュー（Railway と同じ）
send_queue = asyncio.Queue()

@bot.event
async def on_ready():
    log(f"Discord Bot ログイン成功: {bot.user}")
    log("Guild一覧: " + ", ".join([g.name for g in bot.guilds]))

    # ★ 投稿ワーカー開始（1件ずつ1秒ディレイ）
    bot.loop.create_task(send_worker())
    log("Discord 投稿ワーカー開始")

# ============================================================================
# ★ 投稿ワーカー（1件ずつ 1秒間隔で送信）
# ============================================================================
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
            await asyncio.sleep(1)  # ★ 順序安定化の核心
            send_queue.task_done()

# ============================================================================
# Flask API（Render 用）
# ============================================================================

app = Flask(__name__)

@app.route("/post", methods=["POST"])
def post_message():
    data = request.json
    channel_id = data.get("channelId")
    message = data.get("message")

    log(f"/post 受信: channelId={channel_id}, message={message}")

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        log(f"エラー: チャンネル {channel_id} が見つからない")
        return jsonify({"status": "channel_not_found"})

    # ★ キューに積むだけ
    asyncio.run_coroutine_threadsafe(send_queue.put((channel, message)), bot.loop)
    log(f"[QUEUE] 投稿キューに追加（旧API） → {channel_id}")

    return jsonify({"status": "queued"})

@app.route("/postCastleEvent", methods=["POST"])
def post_castle_event():
    data = request.json
    channel_id = data.get("channelId")
    text = data.get("text")

    log(f"/postCastleEvent 受信: channelId={channel_id}, text={text}")

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        log(f"エラー: チャンネル {channel_id} が見つからない")
        return jsonify({"status": "channel_not_found"})

    # ★ キューに積むだけ
    asyncio.run_coroutine_threadsafe(send_queue.put((channel, text)), bot.loop)
    log(f"[QUEUE] 投稿キューに追加（城落ち） → {channel_id}")

    return jsonify({"status": "queued"})

# ============================================================================
# Discord Bot を別スレッドで起動（Render 用）
# ============================================================================

def start_discord_bot():
    token = os.environ["DISCORD_TOKEN"]
    log("Discord Bot スレッド開始")
    asyncio.run(bot.start(token))

threading.Thread(target=start_discord_bot, daemon=True).start()

# ============================================================================
# Flask は app.py 側で gunicorn により起動されるため、
# main.py では Flask を起動しない。
# ============================================================================

log("main.py 読み込み完了（Bot 起動中）")
