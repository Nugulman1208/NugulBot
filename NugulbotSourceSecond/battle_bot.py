import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager
from random import randint
import random
import websockets
import asyncio

class BattleBot(commands.Cog):
    def __init__(self, bot, mongo_uri, db_name):
        self.bot = bot
        self.db_manager = MongoDBManager(mongo_uri, db_name)
        self.messages = self.load_messages()

    def load_messages(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        messages_path = os.path.join(base_dir, 'messages.json')
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def websocket_server(self):
        # 클라이언트의 메시지를 처리하는 핸들러
        async def handle_client(websocket, path):
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                
                # Streamlit에서 notify 신호가 오면 지정된 채널에 메시지를 전송
                if action == "start_battle" or action == "end_battle":
                    channel_id = data.get("channel_id")  # 기본 채널 ID 설정
                    channel_id = int(channel_id)
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(data.get("message"))
                    else:
                        print("Channel not found.")

        self.websocket_server_task = await websockets.serve(handle_client, "0.0.0.0", 8765)
        print("WebSocket server started on ws://0.0.0.0:8765")

    async def cog_load(self):
        # Cog이 로드될 때 웹소켓 서버를 시작합니다.
        await self.websocket_server()

    async def cog_unload(self):
        # Cog이 언로드될 때 웹소켓 서버를 종료합니다.
        self.websocket_server_task.close()
        await self.websocket_server_task.wait_closed()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.bot.user}')
        try:
            # 명령어 동기화
            synced = await self.bot.tree.sync()
            print(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            print(f'Error syncing commands: {e}')

        