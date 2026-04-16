from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

class PostData(BaseModel):
    channelId: str
    message: str

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/post")
def post_to_discord(data: PostData):
    # ここで data.channelId, data.message を使って Discord に転送する
    # まずは動作確認用にそのまま返すだけにしてもOK
    return {"received_channel": data.channelId, "received_message": data.message}
