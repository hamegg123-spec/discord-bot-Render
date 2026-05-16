# app.py ver27.1  _MissingSentinel エラーを完璧に回避

import os
import threading
import asyncio
from flask import Flask, request, jsonify
import discord

# ==========================================
# 1. Flask & Discord 初期化
# ==========================================
app = Flask(__name__)

# Discordのインテント設定
intents = discord.Intents.default()
intents.message_content = True

# グローバルなBotオブジェクト（初期化時にループを紐付けない）
bot = discord.Client(intents=intents)

# Botのステータス管理
bot_status = "STARTING"

# Discord BotのトークンとチャンネルID
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# ==========================================
# 2. Discord イベントハンドラ
# ==========================================
@bot.event
async def on_ready():
    global bot_status
    bot_status = "ONLINE"
    print(f"[Discord] ログインしました！ ユーザー名: {bot.user}")

# ==========================================
# 3. Discord Bot 起動用バックグラウンド関数
# ==========================================
def run_discord_bot():
    """
    独立したスレッド内で、新しいイベントループを作成し、
    そのループ内で直接 bot.start() を呼び出します。
    これにより、Python 3.14 での '_MissingSentinel' エラーを完全に回避します。
    """
    print("[Discord] 専用スレッド内でイベントループを作成中...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if not DISCORD_TOKEN:
        print("[Discord] エラー: DISCORD_TOKEN が設定されていません。")
        return

    print("[Discord] Botのログインシーケンスを開始します...")
    try:
        # loop.run_until_complete 内で start() を動かすことで、
        # discord.py 内部の初期化フラグが正常にセットされます
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[Discord] 起動中にエラーが発生しました: {e}")

# Flask起動前にスレッドを切り離してBotを開始
print("[FlaskAPI] Discord Bot用のバックグラウンドスレッドを準備中...")
bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
bot_thread.start()
print("[FlaskAPI] バックグラウンドスレッドを切り離しました。")

# ==========================================
# 4. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    """生存確認（Ping）用エンドポイント"""
    return f"Bot Status: {bot_status}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    """Cloudflare Workersからのイベントを受信してDiscordへ転送"""
    print("[FlaskAPI] イベントを受信しました。")
    
    if bot_status != "ONLINE":
        print(f"[FlaskAPI] 警告: Botがログインしていません (現在のステータス: {bot_status})")
        return jsonify({"status": "error", "message": "Bot is not ready yet"}), 503

    if not DISCORD_CHANNEL_ID:
        return jsonify({"status": "error", "message": "DISCORD_CHANNEL_ID is not set"}), 500

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # メッセージの組み立て
        # ※データ構造に合わせてお好みで調整してください
        msg = f"【イベント通知】\nデータ: {data}"
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg = (
                f"城イベント発生！\n"
                f"国: {item.get('nation')} | 陣営: {city_info.get('faction')}\n"
                f"場所: {city_info.get('gun')}{city_info.get('city')} ({city_info.get('x')}, {city_info.get('y')})"
            )

        # thread-safeにDiscordのイベントループへメッセージ送信タスクを投げる
        channel_id = int(DISCORD_CHANNEL_ID)
        
        async def send_msg():
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(msg)
                print("[Discord] メッセージの送信に成功しました。")
            else:
                print(f"[Discord] エラー: チャンネルID {channel_id} が見つかりません。")

        # Botが動いているループに対してスレッドセーフに非同期関数を実行
        asyncio.run_coroutine_threadsafe(send_msg(), bot.loop)
        
        return jsonify({"status": "success", "message": "Event forwarded to Discord"}), 200

    except Exception as e:
        print(f"[FlaskAPI] 処理中にエラーが発生しました: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # ローカルテスト用
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
