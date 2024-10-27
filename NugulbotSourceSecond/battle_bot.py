import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager
import random
import websockets
import asyncio
import datetime
from bson import ObjectId
import re

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


    async def dice(self, dice_count, dice_face):
        dice_sum = 0
        for _ in range(dice_count):
            dice_value = random.randint(1, dice_face)
            dice_sum += dice_value
        return dice_sum

    async def replace_formula(self, formula: str, stat: dict):
        # 공백 제거 및 소문자로 변환
        formula = formula.replace(" ", "").lower()
        
        for k, v in stat.items():
            formula = formula.replace(k.lower(), str(v))
            
        return formula

    async def calculate_immediate_skill(self, active_skill_data: dict, behavior_calculate: dict, target_calculate : dict):
        # formula 내 공백 제거 및 변수 치환
        formula = active_skill_data.get("active_skill_formula", "0")
        if not formula.strip():
            formula = "0"
        formula = await self.replace_formula(formula, behavior_calculate)

        # 주사위 패턴 정의 및 계산
        pattern = r"dice\((\d+),(\d+)\)"
        matches = re.findall(pattern, formula)

        for dice_count, dice_face in matches:
            # 치환된 formula 내에서 dice() 호출
            dice_result = await self.dice(int(dice_count), int(dice_face))
            formula = formula.replace(f"dice({dice_count},{dice_face})", str(dice_result), 1)
        # 최종 수식을 평가하여 숫자로 반환
        result = eval(formula)

        # 디스코드로 보낼 description 작성
        description = ""
        behavior_name = ""
        if "user_name" in behavior_calculate.keys():
            behavior_name = behavior_calculate.get("user_name")
        else:
            behavior_name = behavior_calculate.get("monster_name")

        target_name= ""
        if "user_name" in target_calculate.keys():
            target_name = target_calculate.get("user_name")
        else:
            target_name = target_calculate.get("monster_name")
        
        skill_name = active_skill_data.get("active_skill_name")
        skill_type = active_skill_data.get("active_skill_type").lower()

        if skill_type == "attack":
            description = "[{skill_name} (공격)][{behavior_name} → {target_name}] 최종 데미지 : {result}\n"
            result_hp = max(target_calculate.get('hp') - result, 0)
            description += "{target_name} 잔여 체력 : " + str(result_hp)
            target_calculate['hp'] = result_hp
        elif skill_type == "heal":
            description = "[{skill_name} (회복)][{behavior_name} → {target_name}] 최종 회복 : {result}\n"
            result_hp = min(target_calculate.get('max_hp'), target_calculate.get('hp') + result)
            description += "{target_name} 잔여 체력 : " + str(result_hp)
            target_calculate['hp'] = result_hp

        description = description.format(skill_name = skill_name, behavior_name = behavior_name, target_name = target_name, result = str(result))
        return result, description

    @app_commands.command(name="스킬")
    @app_commands.describe(user_skill_name="사용할 스킬의 이름", selected = "타깃")
    async def skill(self, interaction: discord.Interaction, user_skill_name: str, selected : str = "auto"):
        try:
            await interaction.response.defer()  # 응답을 지연시킴
            send_message_list = []  # 메시지를 저장할 리스트

            server_id = str(interaction.guild.id)
            channel_id = str(interaction.channel.id)
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    # user_id 가 user_caculate 에 있는지 확인
                    user_calculate_collection_name = "user_calculate"
                    user_calculate_query = {"user_id": user_id, "server_id": server_id, "del_flag" : False}
                    user_calculate_data = await self.db_manager.find_one_document(session, user_calculate_collection_name, user_calculate_query)
                    if not user_calculate_data:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        await session.abort_transaction()
                        return

                    
                    # 배틀 정보가 있는지 확인
                    battle_collection_name = "battle"
                    battle_query = {"channel_id": channel_id, "server_id": server_id, "del_flag" : False}
                    battle_data = await self.db_manager.find_one_document(session, battle_collection_name, battle_query)

                    if not battle_data:
                        await interaction.followup.send(self.messages['BattleBot.common.not_start_battle'])
                        await session.abort_transaction()
                        return

                    # 스킬 정보가 있는지 확인
                    user_active_skill_collection_name = "user_active_skill"
                    user_active_skill_query = {
                        "user_id" : user_id,
                        "server_id" : server_id,
                        "active_skill_name" : user_skill_name,
                        "del_flag" : False
                    }
                    user_active_skill_data = await self.db_manager.find_one_document(session, user_active_skill_collection_name, user_active_skill_query)

                    if not user_active_skill_data:
                        await interaction.followup.send(self.messages['BattleBot.common.not_found_active_skill'])
                        await session.abort_transaction()
                        return

                    # 타깃 정보
                    target_type = "party"
                    target_column_prefix = "user_"
                    target_collection_name = "user_calculate"
                    target_query = {
                        "del_flag" : False
                    }
                    if user_active_skill_data['active_skill_type'].lower() == "attack":
                        target_type = "enemy"
                        target_column_prefix = "monster_"
                        target_collection_name = "monster_calculate"
                    
                    target_data_list = await self.db_manager.find_documents(session, target_collection_name, target_query)
                    if not target_data_list:
                        await interaction.followup.send(self.messages['BattleBot.common.not_found_target'])
                        await session.abort_transaction()
                        return

                    # 광역, 단일, 자기 자신에 따른 타깃 설정
                    target_result_name_list = list()
                    target_result_list = list()
                    target_name_column = target_column_prefix + "name"
                    # (1) 광역
                    if "all" in user_active_skill_data.get("active_skill_scope").lower():
                        target_result_name_list = [target.get(target_name_column) for target in target_data_list]
                        target_result_list = [target for target in target_data_list]

                    # (2) 단일
                    elif "one" in user_active_skill_data.get("active_skill_scope").lower():
                        # auto 일 경우 체력이 가장 낮은 타깃을 랜덤으로 지정
                        if selected.lower() == "auto":
                            lowest_hp = 2 ** 60
                            lowest_hp_target_list = list()

                            for target in target_data_list:
                                if target.get('hp') < lowest_hp:
                                    lowest_hp = target.get('hp')
                                    lowest_hp_target_list = list()
                                    lowest_hp_target_list.append(target)
                                elif target.get('hp') == lowest_hp:
                                    lowest_hp_target_list.append(target)
                            
                            result_target = random.choice(lowest_hp_target_list)
                            target_result_list.append(result_target)
                            target_result_name_list.append(result_target.get(target_name_column))
                        else:
                            for target in target_data_list:
                                if target.get(target_name_column) == selected:
                                    target_result_name_list.append(target.get(target_name_column))
                                    target_result_list.append(target)

                    # 만일 최종 타깃 설정 리스트가 없다면 에러
                    if len(target_result_name_list) < 1:
                        await interaction.followup.send(self.messages[f'BattleBot.common.not_found_{target_type}'])
                        await session.abort_transaction()
                        return

                    # 수식 계산
                    battle_log_list = list()
                    battle_log_collection_name = "battle_log"

                    user_hate = user_calculate_data.get("hate", 0)
                    user_hate += user_active_skill_data.get("active_skill_hate", 0)

                    for target in target_result_list:
                        active_skill_type = user_active_skill_data.get("active_skill_type").lower()

                        formula_result = 0
                        action_description = ""

                        is_immediate = True
                        if active_skill_type in ["attack", "heal"]:
                            formula_result, action_description = await self.calculate_immediate_skill(user_active_skill_data, user_calculate_data, target)

                        now = datetime.datetime.now()
                        now = int(now.timestamp() * 1000)

                        battle_log = {
                            "server_id" : server_id,
                            "channel_id" : channel_id,
                            "comu_id" : user_calculate_data.get("comu_id"),
                            "action_time" : now,
                            "action_behavior" : user_calculate_data.get("user_name"),
                            "action_bahavior_user_id" : user_calculate_data.get("user_id"),
                            "action_target" : target.get(target_name_column),
                            "action_type" : user_active_skill_data['active_skill_type'],
                            "action_result" : formula_result,
                            "action_description" : action_description
                        }

                        user_hate += formula_result // 10
                        send_message_list.append(action_description)

                        # 로그 기입
                        battle_log_id = await self.db_manager.create_one_document(session, battle_log_collection_name, battle_log)
                        if not battle_log_id:
                            await interaction.followup.send(self.messages['BattleBot.error.battle_log.create'])
                            await session.abort_transaction()
                            return

                        # target 업데이트
                        if is_immediate:
                            target_update_id = await self.db_manager.update_one_document(session, target_collection_name, {"_id" : ObjectId(target.get("_id"))}, target)
                            if not target_update_id:
                                await interaction.followup.send(self.messages['BattleBot.error.target_calculate.update'])
                                await session.abort_transaction()
                                return

                    # 헤이트 추가
                    user_calculate_update_id = await self.db_manager.update_one_document(session, user_calculate_collection_name, {"_id" : ObjectId(user_calculate_data.get("_id"))}, {"hate" : user_hate})
                    
                    if not user_calculate_update_id:
                        await interaction.followup.send(self.messages['BattleBot.error.user_calculate.update'])
                        await session.abort_transaction()
                        return

                    for message in send_message_list:
                        if len(message) < 2000:
                            await interaction.followup.send(message)
                        else:
                            for i in range(0, len(message), 1500):
                                await interaction.followup.send(message[i:i+1500])
                    await session.commit_transaction()

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['common.catch.error'].format(error = e))

    @skill.autocomplete('user_skill_name')
    async def user_skill_name_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    user_skills = await self.db_manager.find_documents(session, "user_active_skill", {
                        "server_id": server_id,  # server_id로 변경
                        "user_id": user_id,
                        "active_skill_name": {'$regex': current, "$options": "i"}
                    })
                    
                    skill_names = [skill["active_skill_name"] for skill in user_skills]
                    unique_skill_names = list(set(skill_names))

                    return [app_commands.Choice(name=skill_name, value=skill_name) for skill_name in unique_skill_names if current.lower() in skill_name.lower()]
        except Exception as e:
            print(e)
            return []
                







                    
                    

        