# main.py
import threading
import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容を読む場合は必須 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot is ready")

def run_bot():
    bot.run(os.getenv("DISCORD_TOKEN"))

threading.Thread(target=run_bot).start()
