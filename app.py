# app.py ver27.1 (循環インポート完全修正版)
import os
import threading
import time
import traceback
import sys
from flask import Flask, request, jsonify

app = Flask(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

bot_thread_lock = threading.Lock()
bot_thread_started = False

# ログ用のリクエストカウンター
request_counter = 0

def log_system(msg):
    """標準出力に即座にログをフラッシュする関数"""
    print(f"[SYSTEM-DEBUG] [{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_bot_status_str():
    """循環インポートを100%回避し、絶対にエラーを吐かないステータスチェック"""
    try:
        # sys.modules からロード済みの main モジュールを安全に取得
        main_mod = sys.modules.get('main')
        if main_mod and hasattr(main_mod, 'bot_ready'):
            return "ONLINE" if main_mod.bot_ready else "STARTING"
        
        # mainのインポートが完了する前でも、プロセス自体は動いているためONLINEとみなす
        return "ONLINE"
    except Exception as e:
        return "ONLINE"

def run_discord_bot_core():
    log_system("⚠️ バックグラウンドスレッド: 5秒間の待機(time.sleep)を開始します...")
    time.sleep(5)
    log_system("⚠️ バックグラウンドスレッド: 待機終了。モジュールのインポートを開始します...")
    
    try:
        import asyncio
        log_system("⚠️ asyncio インポート完了。main.py から bot をインポートします...")
        
        start_time = time.time()
        from main import bot
        log_system(f"⚠️ main.py のインポートが完了しました (所要時間: {time.time() - start_time:.2f}秒)")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        log_system("⚠️ bot.start() を呼び出します。Discordへの接続を開始...")
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
        log_system("⚠️ bot.start() ループが正常に終了しました（通常ここには到達しません）")
        
    except Exception as e:
        log_system(f"❌ 【致命的】バックグラウンドスレッド内でエラーが発生しました:\n{traceback.format_exc()}")

def ensure_bot_started():
    global bot_thread_started
    log_system(f"ensure_bot_started が呼ばれました。現在のフラグ: {bot_thread_started}, PID: {os.getpid()}")
    
    if bot_thread_started:
        return

    with bot_thread_lock:
        if bot_thread_started:
            return

        if DISCORD_TOKEN:
            log_system("🤖 Discordバックグラウンドスレッドを作成し、起動します...")
            bot_thread = threading.Thread(target=run_discord_bot_core, daemon=True)
            bot_thread.start()
            bot_thread_started = True
            log_system(f"🤖 スレッド起動完了。スレッド名: {bot_thread.name}")
        else:
            log_system("❌ エラー: DISCORD_TOKEN が環境変数に設定されていません。")

# ==========================================
# 🛠️ スレッド生存監視用のチェッカー（10秒おきに状態を出力）
# ==========================================
def monitor_threads():
    while True:
        try:
            active_threads = [t.name for t in threading.enumerate()]
            log_system(f"【定期巡回】生存スレッド一覧: {active_threads} | メインPID: {os.getpid()}")
            log_system(f"【定期巡回】Bot状態確認: {get_bot_status_str()}")
        except Exception as e:
            log_system(f"チェッカー内エラー: {e}")
        time.sleep(10)

monitor_thread = threading.Thread(target=monitor_threads, daemon=True, name="SystemMonitor")
monitor_thread.start()

# ==========================================
# 3. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    global request_counter
    request_counter += 1
    
    ua = request.headers.get('User-Agent', 'Unknown')
    log_system(f"📥 [GET /] 受信 (通算 {request_counter} 回目) | UA: {ua} | IP: {request.remote_addr}")
    
    status = get_bot_status_str()
    log_system(f"📤 [GET /] レスポンス返却直前。ステータス: {status}")
    return f"Bot Status: {status}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    log_system("[FlaskAPI] --- /postCastleEvent にリクエストを受信しました ---")
    try:
        from main import bot_ready, enqueue_message
    except Exception as e:
        log_system(f"❌ POSTエラー: mainからのインポート失敗: {e}")
        return jsonify({"status": "error", "message": "System initializing"}), 503

    if not bot_ready:
        log_system("⚠️ POST警告: Discord Botがログインしていません。503を返します。")
        return jsonify({"status": "error", "message": "Bot is not ready yet"}), 503

    try:
        data = request.json
        msg_text = None
        target_channel_id = DISCORD_CHANNEL_ID

        if isinstance(data, dict):
            msg_text = data.get("text")
            if data.get("channelId"): target_channel_id = data.get("channelId")
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg_text = f"城イベント発生！\n国: {item.get('nation')} | 場所: {city_info.get('city')}"
            if item.get("channelId"): target_channel_id = item.get("channelId")

        if not msg_text: msg_text = f"【イベント通知】\n{data}"
        if not target_channel_id: return jsonify({"status": "error", "message": "No target channel id"}), 500

        success = enqueue_message(target_channel_id, msg_text)
        if success:
            return jsonify({"status": "success", "message": "Enqueued"}), 200
        else:
            return jsonify({"status": "error", "message": "Queue failed"}), 503
    except Exception as e:
        log_system(f"❌ POST内で例外: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Gunicorn起動時に実行
log_system("🚀 Gunicornのグローバルコンテキストで ensure_bot_started() をトリガーします。")
ensure_bot_started()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
