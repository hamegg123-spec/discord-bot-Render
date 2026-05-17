# app.py ver27.1  Gunicorn競合とポートスキャンエラーを完璧に回避

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

# グローバルなBotオブジェクト
bot = discord.Client(intents=intents)

# Botのステータス管理
bot_status = "STARTING"
bot_started = False  # スレッドの二重起動防止フラグ
lock = threading.Lock() # スレッド安全のためのロック

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
    """
    print("[Discord] 専用スレッド内でイベントループを作成中...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if not DISCORD_TOKEN:
        print("[Discord] エラー: DISCORD_TOKEN が設定されていません。")
        return

    print("[Discord] Botのログインシーケンスを開始します...")
    try:
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[Discord] 起動中にエラーが発生しました: {e}")

# ==========================================
# 4. Gunicorn / Flask 起動時フック
# ==========================================
@app.before_request
def start_bot_on_first_request():
    """
    最初のアクセス（Renderのヘルスチェック等）があった瞬間に、
    ワーカープロセス内で一度だけ Discord Bot のスレッドを起動します。
    これにより、Gunicornのマスタープロセスとの衝突を防ぎ、Flaskの起動を最優先させます。
    """
    global bot_started
    if not bot_started:
        with lock:
            if not bot_started:
                print("[FlaskAPI] 最初のアクセスを検知。Discord Bot用のバックグラウンドスレッドを起動します...")
                bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
                bot_thread.start()
                bot_started = True
                print("[FlaskAPI] バックグラウンドスレッドを切り離しました。")

# ==========================================
# 5. Flask ルーティング
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
        return jsonify({"status": "error", "message": f"Bot is not ready yet (Status: {bot_status})"}), 503

    if not DISCORD_CHANNEL_ID:
        return jsonify({"status": "error", "message": "DISCORD_CHANNEL_ID is not set"}), 500

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        msg = f"【イベント通知】\nデータ: {data}"
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg = (
                f"城イベント発生！\n"
                f"国: {item.get('nation')} | 陣営: {city_info.get('faction')}\n"
                f"場所: {city_info.get('gun')}{city_info.get('city')} ({city_info.get('x')}, {city_info.get('y')})"
            )

        channel_id = int(DISCORD_CHANNEL_ID)
        
        async def send_msg():
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(msg)
                print("[Discord] メッセージの送信に成功しました。")
            else:
                print(f"[Discord] エラー: チャンネルID {channel_id} が見つかりません。")

        # Botのループが生成されているか安全に確認してタスクを投げる
        if bot.loop and bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(send_msg(), bot.loop)
            return jsonify({"status": "success", "message": "Event forwarded to Discord"}), 200
        else:
            return jsonify({"status": "error", "message": "Discord loop is not running yet"}), 503

    except Exception as e:
        print(f"[FlaskAPI] 処理中にエラーが発生しました: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # ローカルテスト用
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
