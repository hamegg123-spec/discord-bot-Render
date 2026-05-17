# app.py ver27.1 Gunicorn競合とポートスキャンエラーを完璧に回避
import os
import threading
import asyncio
import traceback
from flask import Flask, request, jsonify

# main.py から Bot オブジェクトと関数をインポートして完全に紐付け
from main import bot, bot_ready, enqueue_message

app = Flask(__name__)

# ステータス管理
bot_started = False  # スレッドの二重起動防止フラグ
lock = threading.Lock() # スレッド安全のためのロック

# Discord BotのトークンとデフォルトチャンネルID
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

def get_bot_status_str():
    from main import bot_ready
    return "ONLINE" if bot_ready else "STARTING"

# ==========================================
# 1. Discord Bot 起動用バックグラウンド関数
# ==========================================
def run_discord_bot():
    print("[FlaskAPI] 専用スレッド内でDiscord用イベントループを作成中...", flush=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if not DISCORD_TOKEN:
        print("[FlaskAPI] ❌ エラー: DISCORD_TOKEN が環境変数に設定されていません。", flush=True)
        return

    print("[FlaskAPI] Discord Botのログインシーケンスを開始します...", flush=True)
    try:
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[FlaskAPI] ❌ Discord Bot起動中にエラーが発生しました:\n{traceback.format_exc()}", flush=True)

# ==========================================
# 2. Gunicorn / Flask 起動時フック
# ==========================================
@app.before_request
def start_bot_on_first_request():
    global bot_started
    if not bot_started:
        with lock:
            if not bot_started:
                print("[FlaskAPI] 🚀 最初のアクセス（ヘルスチェック等）を検知。Discord Bot用スレッドを起動します...", flush=True)
                bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
                bot_thread.start()
                bot_started = True
                print("[FlaskAPI] バックグラウンドスレッドの切り離しに成功しました。", flush=True)

# ==========================================
# 3. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    """生存確認（Ping）用エンドポイント"""
    return f"Bot Status: {get_bot_status_str()}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    """Cloudflare Workersからのイベントを受信してDiscordへ転送"""
    print("[FlaskAPI] --- /postCastleEvent にリクエストを受信しました ---", flush=True)
    
    from main import bot_ready
    if not bot_ready:
        print(f"[FlaskAPI] ⚠️ 警告: Discord Botがまだ完全にログインしていません。リクエストを503で返します。", flush=True)
        return jsonify({"status": "error", "message": "Bot is not ready yet. Please wait."}), 503

    try:
        data = request.json
        print(f"[FlaskAPI] 受信データペイロード: {data}", flush=True)
        
        if not data:
            print("[FlaskAPI] ⚠️ エラー: JSONペイロードが空、またはパースできませんでした。", flush=True)
            return jsonify({"status": "error", "message": "No data received or invalid JSON"}), 400

        # --- データ解析処理 ---
        # Workersのログにあった {"channelId": "...", "text": "..."} のパースを最優先
        msg_text = None
        target_channel_id = DISCORD_CHANNEL_ID

        if isinstance(data, dict):
            msg_text = data.get("text")
            if data.get("channelId"):
                target_channel_id = data.get("channelId")
        elif isinstance(data, list) and len(data) > 0:
            # フォールバック: 万が一配列で送られてきた場合の旧パース処理
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg_text = (
                f"城イベント発生！\n"
                f"国: {item.get('nation')} | 陣営: {city_info.get('faction')}\n"
                f"場所: {city_info.get('gun')}{city_info.get('city')} ({city_info.get('x')}, {city_info.get('y')})"
            )
            if item.get("channelId"):
                target_channel_id = item.get("channelId")

        # 最終チェック
        if not msg_text:
            # どちらの形式でもない場合は生データを文字列化
            msg_text = f"【イベント通知（生データ）】\n{data}"

        if not target_channel_id:
            print("[FlaskAPI] ❌ エラー: DISCORD_CHANNEL_ID が指定されていません（環境変数も空です）", flush=True)
            return jsonify({"status": "error", "message": "DISCORD_CHANNEL_ID is not set"}), 500

        print(f"[FlaskAPI] 解析完了 -> チャンネル: {target_channel_id}, 本文: {msg_text[:30]}...", flush=True)

        # main.py のキューに安全に突っ込む
        success = enqueue_message(target_channel_id, msg_text)
        
        if success:
            return jsonify({"status": "success", "message": "Successfully enqueued for Discord"}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to enqueue message (Loop not running)"}), 503

    except Exception as e:
        # ここで例外を100%キャッチしてログに吐き出す
        print(f"[FlaskAPI] ❌ 処理中に深刻なエラーが発生しました:\n{traceback.format_exc()}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
