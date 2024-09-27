# main.py

import discord
from discord.ext import commands
from community_bot import CommunityBot

async def main():
    # 봇 토큰과 MongoDB URI 및 데이터베이스 이름을 설정합니다.
    BOT_TOKEN = 'MTI1ODc3Nzc0NjI4MTA3NDczMA.G0B97M.UWcnnnKDgadaptg5OEObBInI0nxm5dMQK8wdaI'
    MONGO_URI = "mongodb+srv://quietromance1122:1234@nugulbot.xhbdnfk.mongodb.net/?retryWrites=true&w=majority&appName=Nugulbot"
    DB_NAME = "NugulBot"
    
    # 봇을 초기화합니다.
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    # CommunityBot 코그를 추가합니다.
    await bot.add_cog(CommunityBot(bot, MONGO_URI, DB_NAME))
    
    # 봇을 실행합니다.
    await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())