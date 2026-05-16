# main.py
import threading
import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print("Bot is ready")

def run_bot():
    bot.run("DISCORD_TOKEN")

# Bot を別スレッドで起動
threading.Thread(target=run_bot).start()
