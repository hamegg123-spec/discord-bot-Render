# app.py ver27.1.1 (Gunicorn対応・循環インポート完全分離・ログレベル制御・投稿内容ログ追加版)
import os
import threading
import time
import traceback
import sys
from flask import Flask, request, jsonify

# 新設した状態管理モジュールをインポート
import state

app = Flask(__name__)

# 環境変数からログレベルを取得 (デフォルトは INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

bot_thread_lock = threading.Lock()
bot_thread_started = False

# ログ用のリクエストカウンター
request_counter = 0

def log_system(msg, level="DEBUG"):
    """指定されたレベルが現在のLOG_LEVELを満たしている場合のみ出力する関数"""
    levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    current_idx = levels.get(LOG_LEVEL, 1)
    msg_idx = levels.get(level.upper(), 0)

    if msg_idx >= current_idx:
        print(f"[SYSTEM-{level.upper()}] [{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_bot_status_str():
    """独立したstateファイルからフラグを読み取るため、絶対にエラーを吐かない"""
    try:
        return "ONLINE" if state.bot_ready else "STARTING"
    except Exception as e:
        return "ONLINE"

def run_discord_bot_core():
    log_system("⚠️ バックグラウンドスレッド: 5秒間の待機(time.sleep)を開始します...", "INFO")
    time.sleep(5)
    log_system("⚠️ バックグラウンドスレッド: 待機終了。モジュールのインポートを開始します...", "INFO")
    
    try:
        import asyncio
        log_system("⚠️ asyncio インポート完了。main.py から bot をインポートします...", "DEBUG")
        
        start_time = time.time()
        from main import bot
        log_system(f"⚠️ main.py のインポートが完了しました (所要時間: {time.time() - start_time:.2f}秒)", "INFO")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        log_system("⚠️ bot.start() を呼び出します。Discordへの接続を開始...", "INFO")
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
        log_system("⚠️ bot.start() ループが正常に終了しました（通常ここには到達しません）", "WARNING")
        
    except Exception as e:
        log_system(f"❌ 【致命的】バックグラウンドスレッド内でエラーが発生しました:\n{traceback.format_exc()}", "ERROR")

def ensure_bot_started():
    global bot_thread_started
    
    # Gunicornマスタープロセスでの起動をブロック
    if "gunicorn" in sys.argv[0] or os.getenv("SERVER_SOFTWARE", "").startswith("gunicorn"):
        if not request:
            return

    if bot_thread_started:
        return

    with bot_thread_lock:
        if bot_thread_started:
            return

        if DISCORD_TOKEN:
            log_system(f"🤖 ワーカープロセス内でDiscordバックグラウンドスレッドを起動します... (PID: {os.getpid()})", "INFO")
            bot_thread = threading.Thread(target=run_discord_bot_core, daemon=True)
            bot_thread.start()
            bot_thread_started = True
            log_system(f"🤖 スレッド起動完了。スレッド名: {bot_thread.name}", "INFO")
        else:
            log_system("❌ エラー: DISCORD_TOKEN が環境変数に設定されていません。", "ERROR")

# ==========================================
# 🛠️ スレッド生存監視用のチェッカー
# ==========================================
def monitor_threads():
    while True:
        try:
            active_threads = [t.name for t in threading.enumerate()]
            log_system(f"【定期巡回】生存スレッド一覧: {active_threads} | メインPID: {os.getpid()}", "DEBUG")
            log_system(f"【定期巡回】Bot状態確認: {get_bot_status_str()}", "DEBUG")
        except Exception as e:
            log_system(f"チェッカー内エラー: {e}", "ERROR")
        time.sleep(10)

monitor_thread = threading.Thread(target=monitor_threads, daemon=True, name="SystemMonitor")
monitor_thread.start()

# ==========================================
# 3. Flask ルーティング
# ==========================================
@app.route('/', methods=['GET', 'HEAD'])
def index():
    # 実際のWebアクセス（Renderからのヘルスチェック等）が来た瞬間にワーカー側で起動
    ensure_bot_started()
    
    global request_counter
    request_counter += 1
    
    ua = request.headers.get('User-Agent', 'Unknown')
    log_system(f"📥 [GET /] 受信 (通算 {request_counter} 回目) | UA: {ua} | IP: {request.remote_addr}", "DEBUG")
    
    status = get_bot_status_str()
    log_system(f"📤 [GET /] レスポンス返却直前。ステータス: {status}", "DEBUG")
    return f"Bot Status: {status}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    # POSTリクエスト時にも確実にBotの起動を確認
    ensure_bot_started()
    
    log_system(f"[FlaskAPI] --- /postCastleEvent にリクエストを受信しました (PID: {os.getpid()}) ---", "INFO")
    try:
        from main import enqueue_message
    except Exception as e:
        log_system(f"❌ POSTエラー: mainからのインポート失敗: {e}", "ERROR")
        return jsonify({"status": "error", "message": "System initializing"}), 503

    # stateファイルからログイン状態を取得
    if not state.bot_ready:
        log_system(f"⚠️ POST警告: Discord Botがまだログイン完了していません(READYフラグ未立)。503を返します。現在の状態: {get_bot_status_str()}", "WARNING")
        return jsonify({"status": "error", "message": f"Bot is not ready yet (Status: {get_bot_status_str()})"}), 503

    try:
        data = request.json
        log_system(f"[FlaskAPI] 受信JSON: {data}", "DEBUG")

        msg_text = None
        target_channel_id = DISCORD_CHANNEL_ID

        if isinstance(data, dict):
            msg_text = data.get("text")
            if data.get("channelId"):
                target_channel_id = data.get("channelId")
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            city_info = item.get("cityInfo", {})
            msg_text = f"城イベント発生！\n国: {item.get('nation')} | 場所: {city_info.get('city')}"
            if item.get("channelId"):
                target_channel_id = item.get("channelId")

        if not msg_text:
            msg_text = f"【イベント通知】\n{data}"
        if not target_channel_id:
            log_system("❌ POSTエラー: 送信先チャンネルIDが未設定です。", "ERROR")
            return jsonify({"status": "error", "message": "No target channel id"}), 500

        # 実際にDiscordへ送る予定の内容をここでログ出力
        log_system(
            f"[FlaskAPI] Discord送信予定内容:\n"
            f"--- CHANNEL: {target_channel_id} ---\n"
            f"{msg_text}\n"
            f"------------------------------",
            "INFO"
        )

        success = enqueue_message(target_channel_id, msg_text)
        if success:
            log_system("[FlaskAPI] ✅ キュー投入成功。Discordワーカーに処理を委譲しました。", "INFO")
            return jsonify({"status": "success", "message": "Enqueued"}), 200
        else:
            log_system("[FlaskAPI] ❌ キュー投入失敗。Discordワーカーが動作していない可能性があります。", "ERROR")
            return jsonify({"status": "error", "message": "Queue failed"}), 503
    except Exception as e:
        log_system(f"❌ POST内で例外: {traceback.format_exc()}", "ERROR")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
