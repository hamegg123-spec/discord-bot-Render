# app.py ver27.1
import os
import traceback
from flask import Flask, request, jsonify
from main import bot, bot_ready, enqueue_message

app = Flask(__name__)

DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

def get_bot_status_str():
    from main import bot_ready
    return "ONLINE" if bot_ready else "STARTING"

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
