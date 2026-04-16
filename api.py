from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

class PostData(BaseModel):
    channelId: str
    message: str

@app.post("/post")
async def post_message(data: PostData):
    # Worker Service の Discord Bot に送る仕組みを作る
    # 例：Redis / Queue / Webhook など
    return {"status": "received"}
