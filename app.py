# app.py ver27.1 (Render完全統合版)

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
    # bot.start は非同期なので、ループ内で実行
    main.bot.loop.run_until_complete(main.bot.start(token))

@app.before_all_requests  # 最初のアクセスまたは起動時にBotを開始
def start_bot_background():
    if not main.bot.loop.is_running():
        log_api("Discord Botのバックグラウンドループを開始します...")
        t = threading.Thread(target=run_discord, daemon=True)
        t.start()

@app.route('/')
def home():
    return f"Bot Status: {'ONLINE' if main.bot_ready else 'STARTING'}", 200

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
        
        # 【重要】別スレッドのasyncio.Queueへ安全にデータを送り込む魔法の関数
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
