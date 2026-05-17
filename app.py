# app.py ver27.1 (Start Commandがapp:appのままでも100%自動起動する版)
import os
import threading
import asyncio
import traceback
from flask import Flask, request, jsonify
from main import bot, bot_ready, enqueue_message

app = Flask(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# スレッドが重複起動しないためのロックとフラグ
bot_thread_lock = threading.Lock()
bot_thread_started = False

def get_bot_status_str():
    from main import bot_ready
    return "ONLINE" if bot_ready else "STARTING"

# ==========================================
# ⚙️ サーバー起動時に1回だけDiscordを裏で回す安全な仕組み
# ==========================================
def run_discord_bot_core():
    print("[App-Init] 専用スレッド内でDiscordイベントループを起動します...", flush=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[App-Init] ❌ Discord Botが例外で終了しました:\n{traceback.format_exc()}", flush=True)

def ensure_bot_started():
    """Botスレッドが未起動の場合のみ、安全に起動させる関数"""
    global bot_thread_started
    if bot_thread_started:
        return

    with bot_thread_lock:
        if bot_thread_started:
            return

        if DISCORD_TOKEN:
            print("[App-Init] Webワーカープロセス起動を検知。Discordバックグラウンドスレッドを開始します...", flush=True)
            bot_thread = threading.Thread(target=run_discord_bot_core, daemon=True)
            bot_thread.start()
            bot_thread_started = True
        else:
            print("[App-Init] ❌ エラー: DISCORD_TOKEN がありません。Discord Botは起動しません。", flush=True)

# 💡 Renderのヘルスチェック(GET /)やAPIリクエストが届いた瞬間にトリガーして確実に起こす
@app.before_request
def initialize_before_request():
    ensure_bot_started()

# ==========================================
# 3. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return f"Bot Status: {get_bot_status_str()}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    print("[FlaskAPI] --- /postCastleEvent にリクエストを受信しました ---", flush=True)
    
    from main import bot_ready
    if not bot_ready:
        print(f"[FlaskAPI] ⚠️ 警告: Discord Botがログインしていません。503を返します。", flush=True)
        return jsonify({"status": "error", "message": "Bot is not ready yet"}), 503

    try:
        data = request.json
        print(f"[FlaskAPI] 受信データペイロード: {data}", flush=True)
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        msg_text = None
        target_channel_id = DISCORD_CHANNEL_ID

        if isinstance(data, dict):
            msg_text = data.get("text")
            if data.get("channelId"):
                target_channel_id = data.get("channelId")
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg_text = (
                f"城イベント発生！\n"
                f"国: {item.get('nation')} | 陣営: {city_info.get('faction')}\n"
                f"場所: {city_info.get('gun')}{city_info.get('city')} ({city_info.get('x')}, {city_info.get('y')})"
            )
            if item.get("channelId"):
                target_channel_id = item.get("channelId")

        if not msg_text:
            msg_text = f"【イベント通知】\n{data}"

        if not target_channel_id:
            return jsonify({"status": "error", "message": "No target channel id"}), 500

        print(f"[FlaskAPI] キュー転送準備完了 -> チャンネル: {target_channel_id}", flush=True)

        success = enqueue_message(target_channel_id, msg_text)
        if success:
            return jsonify({"status": "success", "message": "Enqueued"}), 200
        else:
            return jsonify({"status": "error", "message": "Queue failed"}), 503

    except Exception as e:
        print(f"[FlaskAPI] ❌ 致命的エラー:\n{traceback.format_exc()}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # ローカル実行時、または明示的なpython app.py起動時にもBotを起動
    ensure_bot_started()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
