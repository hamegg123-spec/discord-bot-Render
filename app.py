# app.py ver27.2 (ログ超強化版)

from flask import Flask, request, jsonify
import asyncio
import time
import main  # bot, send_queue, bot_ready を使う

app = Flask(__name__)

def wait_for_bot_ready(timeout=10):
    """Botが準備完了になるまでログを吐きながら待つ関数"""
    start_time = time.time()
    attempt = 0
    while not main.bot_ready:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            main.log(f"[CHECK] 🔴 Bot準備待ちタイムアウト! ({timeout}秒経過) 503エラーを返します")
            return False
        
        attempt += 1
        if attempt % 2 == 1:  # 1秒ごとにログを出力
            main.log(f"[CHECK] ⏳ Botのログインを待っています... 経過時間: {elapsed:.1f}秒 (bot_ready={main.bot_ready})")
        
        time.sleep(0.5)
    
    main.log(f"[CHECK] 🟢 Bot準備完了を確認しました！ 待機時間: {time.time() - start_time:.1f}秒")
    return True

@app.get("/")
def ping():
    # Renderのヘルスチェック用
    status = "READY" if main.bot_ready else "BOT_NOT_READY"
    return f"ok - {status}"

@app.post("/post")
def post_message():
    main.log("[API] /post リクエストを受信しました")
    if not wait_for_bot_ready():
        return jsonify({"status": "bot_not_ready", "reason": "timeout_waiting_for_ready"}), 503

    data = request.json or {}
    channel_id = data.get("channelId")
    message = data.get("message")

    main.log(f"/post 処理開始: channelId={channel_id}, message={message}")

    channel = main.bot.get_channel(int(channel_id))
    if channel is None:
        main.log(f"エラー: チャンネル {channel_id} が見つからない")
        return jsonify({"status": "channel_not_found"}), 404

    asyncio.run_coroutine_threadsafe(
        main.send_queue.put((channel, message)),
        main.bot.loop
    )
    main.log(f"[QUEUE] 投稿キューに追加（旧API） → {channel_id}")
    return jsonify({"status": "queued"})

@app.post("/postCastleEvent")
def post_castle_event():
    main.log("[API] /postCastleEvent (城落ち) リクエストを受信しました")
    if not wait_for_bot_ready():
        return jsonify({"status": "bot_not_ready", "reason": "timeout_waiting_for_ready"}), 503

    data = request.json or {}
    channel_id = data.get("channelId")
    text = data.get("text")

    main.log(f"/postCastleEvent 処理開始: channelId={channel_id}, text={text}")

    channel = main.bot.get_channel(int(channel_id))
    if channel is None:
        main.log(f"エラー: チャンネル {channel_id} が見つからない")
        return jsonify({"status": "channel_not_found"}), 404

    asyncio.run_coroutine_threadsafe(
        main.send_queue.put((channel, text)),
        main.bot.loop
    )
    main.log(f"[QUEUE] 投稿キューに追加（城落ち） → {channel_id}")
    return jsonify({"status": "queued"})
