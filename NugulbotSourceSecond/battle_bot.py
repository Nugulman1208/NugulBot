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
                if action in {"start_battle", "end_battle", "send_message"}:
                    channel_id = data.get("channel_id")  # 기본 채널 ID 설정
                    channel_id = int(channel_id)
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        full_message = data.get("message")
                        
                        # 메시지를 2000자 이하로 나누어 전송
                        for i in range(0, len(full_message), 2000):
                            chunk = full_message[i:i+2000]
                            await channel.send(chunk)
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

        if "hate" in formula:
            formula = formula.replace("hate", stat.get("hate", 0))
            
        return formula

    async def simple_formula_calculator(self, formula : str, stat: dict):
        formula = await self.replace_formula(formula, stat)
        pattern = r"dice\(([^,]+),([^,]+)\)"
        matches = re.findall(pattern, formula)

        for dice_count, dice_face in matches:
            # 치환된 formula 내에서 dice() 호출
            dice_result = await self.dice(int(eval(dice_count)), int(eval(dice_face)))
            formula = formula.replace(f"dice({dice_count},{dice_face})", str(dice_result), 1)

        # 최종 수식을 평가하여 숫자로 반환
        result = int(eval(formula))

        return result

    async def calculate_skill(self, active_skill_data: dict, behavior_calculate: dict, target_calculate : dict, battle_status_list : list = []):
        # formula 내 공백 제거 및 변수 치환
        formula = active_skill_data.get("active_skill_formula", "0")
        if not formula.strip():
            formula = "0"
        formula = await self.replace_formula(formula, behavior_calculate)

        # 주사위 패턴 정의 및 계산
        pattern = r"dice\(([^,]+),([^,]+)\)"
        matches = re.findall(pattern, formula)

        for dice_count, dice_face in matches:
            # 치환된 formula 내에서 dice() 호출
            dice_result = await self.dice(int(eval(dice_count)), int(eval(dice_face)))
            formula = formula.replace(f"dice({dice_count},{dice_face})", str(dice_result), 1)

        # 최종 수식을 평가하여 숫자로 반환
        result = int(eval(formula))

        # 디스코드로 보낼 description 작성
        description = f"기본 데미지 : {result}\n"

        behavior_name = ""
        if "user_name" in behavior_calculate.keys():
            behavior_name = behavior_calculate.get("user_name")
        else:
            behavior_name = behavior_calculate.get("monster_name")

        target_name= ""
        target_status_list = list()

        if "user_name" in target_calculate.keys():
            target_name = target_calculate.get("user_name")
            target_status_list = [status for status in battle_status_list if status.get("status_target") == target_name or status.get("status_target") == behavior_name]
        else:
            target_name = target_calculate.get("monster_name")
            target_status_list = [status for status in battle_status_list if status.get("status_target") == target_name or status.get("status_target") == behavior_name]

        # 버프 수치 추가
        for status in target_status_list:
            if status.get("status_type") != "buff":
                continue

            if status.get("status_target") != behavior_name:
                continue
            
            status_formula = status.get("status_formula").lower()
            status_formula.replace("result", str(result))
            result = int(eval(status_formula))

            description += f"버프 수치 추가 데미지 : {result}\n"
            status['del_flag'] = True
        
        skill_name = active_skill_data.get("active_skill_name")
        skill_type = active_skill_data.get("active_skill_type").lower()

        if skill_type == "attack":
            # target_status : defense 반영
            for status in target_status_list:
                if result <= 0:
                    break

                if status.get("status_type") == "defense":
                    if status.get("status_target") != target_name:
                        continue

                    status_formula = status.get("status_formula")

                    if status_formula <= 0:
                        continue

                    if result <= status_formula:
                        status['status_formula'] -= result
                        description += f"[방어] 데미지 : {result} → 0 (잔여 방어막 : {status['status_formula']})\n"
                        result = 0
                        break
                    else:
                        org_result = result
                        result -= status['status_formula']
                        status['status_formula'] = 0
                        description += f"[방어] 데미지 : {org_result} → {result} (잔여 방어막 : {status['status_formula']})\n"
                        status['del_flag'] = True

            description += "[{skill_name} (공격)][{behavior_name} → {target_name}] 최종 데미지 : {result}\n"
            result_hp = max(target_calculate.get('hp') - result, 0)
            description += "{target_name} 잔여 체력 : " + str(result_hp)
            target_calculate['hp'] = result_hp
        elif skill_type == "heal":
            description = "[{skill_name} (회복)][{behavior_name} → {target_name}] 최종 회복 : {result}\n"
            result_hp = min(target_calculate.get('max_hp'), target_calculate.get('hp') + result)
            description += "{target_name} 잔여 체력 : " + str(result_hp)
            target_calculate['hp'] = result_hp
        elif skill_type == "defense":
            description = "[{skill_name} (방어)][{behavior_name} → {target_name}] 최종 방어막 : {result} (2턴)\n"
        elif skill_type == "increase_hate":
            org_hate = target_calculate.get("hate", 0)
            new_hate = org_hate + result
            description = "[{skill_name} (헤이트 증가)][{behavior_name} → {target_name}] 헤이트 {result} 증가\n"
            description += "{target_name} 헤이트 변화 : " + f"{org_hate} → {new_hate}"
            target_calculate['hate'] = new_hate
        elif skill_type == "decrease_hate":
            org_hate =  target_calculate.get("hate", 0)
            new_hate = max(org_hate - result, 0)
            description = "[{skill_name} (헤이트 감소)][{behavior_name} → {target_name}] 헤이트 {result} 감소\n"
            description += "{target_name} 헤이트 변화 : " + f"{org_hate} → {new_hate}"
            target_calculate['hate'] = new_hate

        org_id_dict = {status["_id"]: status for status in battle_status_list}
        new_id_dict = {status["_id"]: status for status in target_status_list}

        org_id_dict.update(new_id_dict)
        battle_status_list = list(org_id_dict.values())

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

                    # HP 가 0 이라면 스킬 사용 x
                    if user_calculate_data.get("hp", 0) <= 0:
                        await interaction.followup.send(self.messages['BattleBot.skill.zero_hp'])
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

                    # 턴 수행을 했는지 안 했는지 확인
                    battle_log_collection_name = "battle_log"
                    battle_log_validate_query = {
                        "action_behavior_user_id" : user_id,
                        "battle_id" : ObjectId(str(battle_data.get("_id"))),
                        "current_turn" : int(battle_data.get("current_turn")),
                        "action_type" : {
                            "$ne" : "use_item"
                        }
                    }

                    battle_log_validate_data = await self.db_manager.find_one_document(session, battle_log_collection_name, battle_log_validate_query)
                    if battle_log_validate_data:
                        await self.db_manager.update_one_document(session, user_calculate_collection_name, user_calculate_query, {'hp' : 0})
                        await interaction.followup.send(self.messages['BattleBot.skill.already_skill_use'])
                        await session.commit_transaction()
                        return

                    

                    # 배틀 스테이터스를 끌고 온다
                    battle_status_collection_name = "battle_status"
                    battle_status_query = {
                        "comu_id" : battle_data.get("comu_id"),
                        "del_flag" : False,
                        "battle_id" : ObjectId(str(battle_data.get("_id"))),
                        "status_end_turn" :{
                            "$gte" : battle_data.get("current_turn")
                        }
                    }


                    battle_status_list = await self.db_manager.find_documents(session, battle_status_collection_name, battle_status_query)
                    if not battle_status_list:
                        battle_status_list = list()

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
                        "del_flag" : False,
                        "hp" : {
                            "$gt" : 0
                        }
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
                        # (1) - 1 아군 대상 광역 + 아군 대상 조건이 존재할 때
                        target_result_name_list = [target.get(target_name_column) for target in target_data_list]
                        target_result_list = [target for target in target_data_list]

                        if target_type == 'party' and user_active_skill_data.get("active_skill_condition"):
                            active_skill_condition = user_active_skill_data.get("active_skill_condition")
                            target_result_list = [target for target in target_result_list if target.get("battle_type") in active_skill_condition]

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
                    # (3) 자신
                    elif "me" in user_active_skill_data.get("active_skill_scope").lower():
                        target_result_list.append(user_calculate_data)
                        target_result_name_list.append(user_calculate_data.get("user_name"))

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

                        battle_update_type = "immediate"
                        if active_skill_type in ["defense"]:
                            battle_update_type = "status"
                        elif active_skill_type in ['heal', "attack"] and user_active_skill_data.get("active_dot_formula", None):
                            battle_update_type = "status_immediate"
                        formula_result, action_description = await self.calculate_skill(user_active_skill_data, user_calculate_data, target, battle_status_list)

                        now = datetime.datetime.now()
                        now = int(now.timestamp() * 1000)

                        if str(user_calculate_data.get("_id")) == str(target.get("_id")):
                            if "increase_hate" == active_skill_type:
                                user_hate += formula_result
                            elif "decrease_hate" == active_skill_type:
                                user_hate = max(0, user_hate - formula_result)
                            else:
                                user_hate += formula_result // 10
                        else:
                            if active_skill_type not in ["increase_hate", "decrease_hate"]:
                                user_hate += formula_result // 10            

                        battle_log = {
                            "server_id" : server_id,
                            "channel_id" : channel_id,
                            "comu_id" : user_calculate_data.get("comu_id"),
                            "battle_name" : battle_data.get("battle_name"),
                            "current_turn" : battle_data.get("current_turn"),
                            "battle_id" : battle_data.get("_id"),
                            "action_time" : now,
                            "action_behavior_name" : user_calculate_data.get("user_name"),
                            "action_behavior_user_id" : user_calculate_data.get("user_id"),
                            "action_behavior_type" : "user",
                            "action_target_type" : target_type,
                            "action_target_name" : target.get(target_name_column),
                            "action_type" : user_active_skill_data['active_skill_type'],
                            "action_result" : formula_result,
                            "action_description" : action_description
                        }
                        
                        send_message_list.append(action_description)

                        # 로그 기입
                        battle_log_id = await self.db_manager.create_one_document(session, battle_log_collection_name, battle_log)
                        if not battle_log_id:
                            await interaction.followup.send(self.messages['BattleBot.error.battle_log.create'])
                            await session.abort_transaction()
                            return

                        # target 업데이트 (즉발이면 calculate 에 직접 넣어지고 아니면 battle_status 에 보관 된다.)
                        if "immediate" in battle_update_type:
                            target_update_id = await self.db_manager.update_one_document(session, target_collection_name, {"_id" : ObjectId(target.get("_id"))}, target)
                            if not target_update_id:
                                await interaction.followup.send(self.messages['BattleBot.error.target_calculate.update'])
                                await session.abort_transaction()
                                return
                        if "status" in battle_update_type:
                            if active_skill_type == "defense":
                                status_formula = formula_result
                                status_type = active_skill_type
                                status_end_turn = battle_data.get("current_turn") + 1
                                status_name = "방어"
                            else:
                                status_formula = user_active_skill_data.get("active_dot_formula", None)
                                status_type = "dot_" + active_skill_type
                                status_end_turn = battle_data.get("current_turn") + user_active_skill_data.get("active_dot_turn") - 1

                                dot_result_list = list()

                                for _ in range(0, user_active_skill_data.get("active_dot_turn")):
                                    dot_result = await self.simple_formula_calculator(status_formula, user_calculate_data)
                                    dot_result_list.append(dot_result)

                                status_formula = dot_result_list
                                status_name = user_active_skill_data.get("active_dot_name")

                            battle_status_data = {
                                "server_id" : server_id,
                                "channel_id" : channel_id,
                                "comu_id" : user_calculate_data.get("comu_id"),
                                "battle_name" : battle_data.get("battle_name"),
                                "battle_id" : ObjectId(str(battle_data.get("_id"))),
                                "status_type" : status_type,
                                "status_target_collection_name" : target_collection_name,
                                "status_formula" : status_formula,
                                "status_target" : target.get(target_name_column),
                                "status_end_turn" : status_end_turn,
                                "status_behavior_name" : user_calculate_data.get("user_name"),
                                "status_bahavior_user_id" : user_calculate_data.get("user_id"),
                                "status_name" : status_name,
                                "del_flag" : False
                            }

                            target_update_id = await self.db_manager.create_one_document(session, "battle_status", battle_status_data)
                            if not target_update_id:
                                await interaction.followup.send(self.messages['BattleBot.error.battle_status.create'])
                                await session.abort_transaction()
                                return

                    # 스테이터스 업데이트
                    for status in battle_status_list:
                        status_id = str(status.pop("_id"))
                        status['battle_id'] = ObjectId(str(status['battle_id']))
                        update_battle_status_result = await self.db_manager.update_one_document(session,"battle_status", {"_id" : ObjectId(status_id)}, status)
                    # 헤이트 추가
                    user_calculate_update_id = await self.db_manager.update_one_document(session, user_calculate_collection_name, {"_id" : ObjectId(user_calculate_data.get("_id"))}, {"hate" : user_hate})
                    
                    if not user_calculate_update_id:
                        await interaction.followup.send(self.messages['BattleBot.error.user_calculate.update'])
                        await session.abort_transaction()
                        return

                    final_message = ""
                    for message in send_message_list:
                        final_message += message
                        final_message += "\n\n"

                    final_message += f"현재 {user_calculate_data.get("user_name")}의 헤이트 : {user_hate}"

                    if len(final_message) < 2000:
                        await interaction.followup.send(final_message)
                    else:
                        for i in range(0, len(final_message), 2000):
                            await interaction.followup.send(final_message[i:i+2000])
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

    @skill.autocomplete('selected')
    async def selected_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)
            channel_id = str(interaction.channel.id)
            user_id = str(interaction.user)
            
            # USER_SKILL_NAME을 기준으로 동적으로 선택지 구성
            user_skill_name = None
            for data in interaction.data.get("options"):
                if data.get("name") == "user_skill_name":
                    user_skill_name = data.get("value")

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    battle_collection_name = "battle"
                    battle_query = {"channel_id": channel_id, "server_id": server_id, "del_flag" : False}
                    battle_data = await self.db_manager.find_one_document(session, battle_collection_name, battle_query)

                    monster_list = list()

                    user_skill = await self.db_manager.find_one_document(session, "user_active_skill", {
                        "server_id": server_id,  # server_id로 변경
                        "user_id": user_id,
                        "active_skill_name": user_skill_name,
                        "del_flag" : False
                    })
                    
                    if user_skill.get("active_skill_type", None) == "attack" and user_skill.get("active_skill_scope").startswith("one"):
                        monster_calculate_collection_name = "monster_calculate"
                        monster_calculate_query = {"server_id": server_id, "del_flag" : False, "hp" : {"$gt" : 0}}
                        monster_calculate_data = await self.db_manager.find_documents(session, monster_calculate_collection_name, monster_calculate_query)

                        for monster in monster_calculate_data:
                            monster_list.append(monster.get("monster_name"))

                        return [app_commands.Choice(name=monster_name, value=monster_name) for monster_name in monster_list if current.lower() in monster_name.lower()]
                    elif user_skill.get("active_skill_type", None) in ["heal", "defense"] and user_skill.get("active_skill_scope").startswith("one"):
                        user_calculate_collection_name = "user_calculate"
                        user_calculate_query = {"server_id": server_id, "del_flag" : False, "hp" : {"$gt" : 0}}
                        user_calculate_data = await self.db_manager.find_documents(session, user_calculate_collection_name, user_calculate_query)

                        return [app_commands.Choice(name=user.get("user_name"), value=user.get("user_name")) for user in user_calculate_data if current.lower() in user.get("user_name").lower()]
                    elif user_skill.get("active_skill_scope").startswith("all"):
                        return [app_commands.Choice(name="auto", value="auto")]
        except Exception as e:
            print(e)
            return []
                







                    
                    

        