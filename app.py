# app.py ver27.1 (Render完全統合・クラッシュ修正版)

import os
import asyncio
import threading
import datetime
from flask import Flask, request, jsonify
import main  # main.py をインポート

app = Flask(__name__)

def log_api(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [FlaskAPI] {msg}")

# Discord Botを別スレッドのイベントループで安全に回すための設定
def run_discord():
    asyncio.set_event_loop(main.bot.loop)
    token = os.environ.get("DISCORD_TOKEN")
    try:
        main.bot.loop.run_until_complete(main.bot.start(token))
    except Exception as e:
        log_api(f"❌ Discord Botループ終了エラー: {e}")

# 🚀 アプリ起動時（リクエストを待つ前）に、自動で一度だけBotを起動する構造に変更
log_api("Discord Botのバックグラウンドループを準備中...")
t = threading.Thread(target=run_discord, daemon=True)
t.start()
log_api("Discord Botのバックグラウンドスレッドを切り離しました。")

@app.route('/')
def home():
    # 状態をテキストで返す
    status = "ONLINE" if main.bot_ready else "STARTING"
    return f"Bot Status: {status}", 200

@app.route('/postCastleEvent', methods=['POST'])
def post_castle_event():
    log_api("/postCastleEvent 受信しました")
    
    # 10秒間の起動待ち
    for i in range(10):
        if main.bot_ready:
            break
        log_api(f"⏳ Botのログインを待っています... ({i}秒経過)")
        import time
        time.sleep(1)
        
    if not main.bot_ready:
        log_api("🔴 Botログイン待ちタイムアウト。503を返します。")
        return jsonify({"status": "error", "message": "Bot is not ready"}), 503

    try:
        data = request.json or {}
        channel_id = int(data.get("channelId", 0))
        text = data.get("text", "")
        
        channel = main.bot.get_channel(channel_id)
        if not channel:
            log_api(f"❌ チャンネルが見つかりません: {channel_id}")
            return jsonify({"status": "error", "message": "Channel not found"}), 400

        log_api(f"📥 スレッド安全にキューへ追加します → Channel: {channel_id}")
        
        # 別スレッドのasyncio.Queueへ安全にデータを送り込む
        asyncio.run_coroutine_threadsafe(
            main.send_queue.put((channel, text)), 
            main.bot.loop
        )
        
        return jsonify({"status": "success", "message": "Queued successfully"}), 200
        
    except Exception as e:
        log_api(f"❌ エラー発生: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
