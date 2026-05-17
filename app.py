# app.py ver27.1 (ヘルスチェック完全最優先・バックグラウンド遅延インポート版)
import os
import threading
import time
import traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# スレッド重複防止
bot_thread_lock = threading.Lock()
bot_thread_started = False

def get_bot_status_str():
    # 応答を極限まで軽くするため、try-exceptで安全にステータスを取得
    try:
        from main import bot_ready
        return "ONLINE" if bot_ready else "STARTING"
    except:
        return "INITIALIZING"

def run_discord_bot_core():
    # Renderが完全に「起動成功」と認識するまで数秒待つ（超重要）
    time.sleep(5)
    print("[App-Init] 専用スレッド内でDiscordイベントループを起動します...", flush=True)
    
    # 💡 重いインポートと起動処理を、このバックグラウンドスレッドの中で初めて実行する
    try:
        import asyncio
        from main import bot
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[App-Init] ❌ Discord Botが例外で終了しました:\n{traceback.format_exc()}", flush=True)

def ensure_bot_started():
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
            print("[App-Init] ❌ エラー: DISCORD_TOKEN がありません。", flush=True)

# ⚠️ 削除: @app.before_request の仕組みはRenderのチェックを遅らせるため撤去します

# ==========================================
# 3. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    # 届いた瞬間に1ミリ秒で即答する（これでRenderのチェックを100%パスします）
    return f"Bot Status: {get_bot_status_str()}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    print("[FlaskAPI] --- /postCastleEvent にリクエストを受信しました ---", flush=True)
    
    try:
        from main import bot_ready, enqueue_message
    except Exception as e:
        return jsonify({"status": "error", "message": "System initializing"}), 503

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

# Gunicorn（Webサーバー）のメインプロセス起動直後に一度だけ実行させる
ensure_bot_started()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
