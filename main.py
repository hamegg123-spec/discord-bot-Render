
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class PostData(BaseModel):
    channelId: str
    message: str

@app.post("/post")
async def post_message(data: PostData):
    # Bot 用サービスの URL
    worker_url = "https://discord-bot-production-fcc0.up.railway.app/post"

    r = requests.post(worker_url, json={
        "channelId": data.channelId,
        "message": data.message
    })

    return {
        "status": "forwarded",
        "worker_status": r.status_code
    }




