# main.py

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os


from user_info_bot import UserInfoBot
from store_bot import StoreBot
from battle_bot import BattleBot

load_dotenv()

async def main():
    # 봇 토큰과 MongoDB URI 및 데이터베이스 이름을 설정합니다.
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("DB_NAME")
    
    # 봇을 초기화합니다.
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    # ItemBuyBot 코그를 추가합니다.
    await bot.add_cog(UserInfoBot(bot, MONGO_URI, DB_NAME))
    await bot.add_cog(StoreBot(bot, MONGO_URI, DB_NAME))
    await bot.add_cog(BattleBot(bot, MONGO_URI, DB_NAME))
    
    # 봇을 실행합니다.
    await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())