# app.py
from flask import Flask
app = Flask(__name__)

@app.get("/")
def ping():
    return "ok"

# ここで Bot を起動
import main
