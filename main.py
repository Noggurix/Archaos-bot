import os
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

extensions_list = [
	'cogs.statroll',
	'cogs.dice.cog',
	'cogs.table.cog',
]

@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} conectado!")

    synced = await bot.tree.sync()
    print(f"Sincronizados {len(synced)} comandos!")

async def main():
    for ext in extensions_list:
        await bot.load_extension(ext)

    await bot.start(TOKEN)

asyncio.run(main())
