# app.py ver27.1 (Flask API + Bot 呼び出し)

from flask import Flask, request, jsonify
import asyncio
import main  # bot と send_queue を使う

app = Flask(__name__)

@app.get("/")
def ping():
    return "ok"

@app.post("/post")
def post_message():
    data = request.json or {}
    channel_id = data.get("channelId")
    message = data.get("message")

    main.log(f"/post 受信: channelId={channel_id}, message={message}")

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
    data = request.json or {}
    channel_id = data.get("channelId")
    text = data.get("text")

    main.log(f"/postCastleEvent 受信: channelId={channel_id}, text={text}")

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
