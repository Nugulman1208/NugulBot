import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager
from google_sheet_manager import GoogleSheetManager
from cachetools import TTLCache
from random import randint
import random

class CommunityBot(commands.Cog):
    def __init__(self, bot, mongo_uri, db_name):
        self.bot = bot
        self.db_manager = MongoDBManager(mongo_uri, db_name)
        self.sheet_manager = GoogleSheetManager()
        self.messages = self.load_messages()


    def load_messages(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        messages_path = os.path.join(base_dir, 'messages.json')
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_ready(self):
        print('Syncing commands...')
        try:
            # 모든 서버에서 기존 명령어 제거
            self.bot.tree.clear_commands(guild=None)
            
            # 슬래시 명령어 추가
            self.bot.tree.add_command(self.start_community)
            self.bot.tree.add_command(self.comu_information)
            self.bot.tree.add_command(self.data_update_from_sheet)
            self.bot.tree.add_command(self.register_user)
            self.bot.tree.add_command(self.purchase)
            self.bot.tree.add_command(self.inventory)
            self.bot.tree.add_command(self.accrue)

            self.bot.tree.add_command(self.my_info)
            self.bot.tree.add_command(self.start_battle)
            self.bot.tree.add_command(self.end_battle)
            self.bot.tree.add_command(self.use_item)
            self.bot.tree.add_command(self.skill)
            self.bot.tree.add_command(self.end_phase)
            self.bot.tree.add_command(self.emergency_heal)
            self.bot.tree.add_command(self.transfer_item)
            self.bot.tree.add_command(self.get_slip_data)
            
            # 동기화
            synced = await self.bot.tree.sync()
            print(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            print(f'Error syncing commands: {e}')
        print(f'We have logged in as {self.bot.user}')


    @app_commands.command(name='커뮤시작')
    @app_commands.describe(comu_name="커뮤 이름", email="이메일(구글 이메일)")
    async def start_community(self, interaction: discord.Interaction, comu_name: str, email: str):
        await interaction.response.defer()  # 즉시 응답을 지연시킴

        success = True
        sheet_url = ""

        # channel_id 대신 server_id를 사용
        server_id = str(interaction.guild.id)
        leader_name = str(interaction.user)

        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 디버깅 메시지
                    await interaction.followup.send("커뮤니티 이름을 찾고 있다구리...")

                    collection_name = "community"
                    document = await self.db_manager.find_one_document(session, collection_name, {"server_id": server_id})
                    if document is not None:
                        await interaction.followup.send(self.messages["community_already_started"])
                        await session.abort_transaction()
                        return

                    # 디버깅 메시지
                    await interaction.followup.send("서버 아이디를 체크하고 있다구리...")

                    document = await self.db_manager.find_one_document(session, collection_name, {"comu_name": comu_name})
                    if document is not None:
                        await interaction.followup.send(self.messages["community_name_conflict"])
                        await session.abort_transaction()
                        return

                    # 디버깅 메시지
                    await interaction.followup.send("커뮤 이름을 체크하고 있다구리...")

                    copied_sheet_id, success = await self.sheet_manager.copy_file_and_set_permission(comu_name, email)

                    if not success:
                        await interaction.followup.send(self.messages["sheet_copy_failure"])
                        await session.abort_transaction()
                        return

                    # 디버깅 메시지
                    await interaction.followup.send("시트 정보를 가져오고 있다구리...")

                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{copied_sheet_id}"

                    modified_count, upserted_id = await self.db_manager.update_document(
                        session, collection_name, {"server_id": server_id}, {"server_id": server_id, "comu_name": comu_name, "leader_name": leader_name, "sheet_id": copied_sheet_id, "leader_email": email}
                    )

                    # 디버깅 메시지
                    await interaction.followup.send("DB를 업데이트 하고 있다구리...")

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages["community_start_success"].format(comu_name=comu_name, sheet_url=sheet_url))

                except Exception as e:
                    print(e)
                    await session.abort_transaction()
                    await interaction.followup.send("An error occurred while processing this command.", ephemeral=True)
                    return


    
    @app_commands.command(name="커뮤정보")
    async def comu_information(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            # channel_id 대신 server_id를 사용
            server_id = str(interaction.guild.id)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    # server_id를 사용하여 커뮤니티 정보 조회
                    result = await self.db_manager.get_comu_info(session, server_id)
                    if result is None:
                        await interaction.followup.send(self.messages["community_not_started"])
                        return
                    
                    comu_name = result['comu_name']
                    leader_name = result['leader_name']
                    leader_email = result['leader_email']
                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{result['sheet_id']}"

                    sendStr = self.messages["community_information"].format(
                        comu_name=comu_name,
                        leader_name=leader_name,
                        leader_email=leader_email,
                        sheet_url=sheet_url
                    )

                    await interaction.followup.send(sendStr)
        except Exception as e:
            print(e)
            traceback.print_exc()
            await interaction.followup.send(self.messages["data_cannot_get"])


    @app_commands.command(name="데이터갱신")
    async def data_update_from_sheet(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        channel_id = str(interaction.channel.id)  # 채널 ID를 가져옴

        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    
                    # 1. 기존에 channel_id로 저장된 데이터를 server_id로 업데이트
                    collections = await self.db_manager.database.list_collection_names()
                    for collection_name in collections:
                        collection = self.db_manager.database[collection_name]
                        
                        # 채널 ID가 같은 모든 문서의 channel_id를 server_id로 변경
                        update_result = await collection.update_many(
                            {"channel_id": channel_id},
                            {"$set": {"server_id": server_id}},
                            session=session
                        )
                        
                        # 업데이트된 문서들에서 channel_id 필드를 제거 (선택 사항)
                        await collection.update_many(
                            {"channel_id": channel_id},
                            {"$unset": {"channel_id": ""}},
                            session=session
                        )
                    
                    # 2. 커뮤니티 정보 가져오기
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["community_not_started"])
                        return

                    sheet_id = comu_info['sheet_id']
                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{sheet_id}"
                    comu_name = comu_info['comu_name']

                    calculate_data = []
                    for sheet_name in self.sheet_manager.SHEET_NAME_LIST:
                        rowList, dataList, success = await self.sheet_manager.get_data_from_google_sheet(sheet_id, sheet_name)
                        if not success:
                            await interaction.followup.send(self.messages['sheet_get_failure'])
                            await session.abort_transaction()
                            return

                        collection_name = sheet_name.replace("_INFORMATION", "").lower()
                        dataList = [{k.lower(): v for k, v in d.items()} for d in dataList]
                        dataList = [{'server_id': server_id, 'comu_name': comu_name, **d} for d in dataList]
                        dataList = await self.convert_numeric_strings_to_int(dataList)

                        delete_result = await self.db_manager.remove_document(session, collection_name, {"server_id": server_id})

                        update_result = await self.db_manager.create_documents(session, collection_name, dataList)
                        if update_result is None:
                            await interaction.followup.send(self.messages['data_update_failure'])
                            await session.abort_transaction()
                            return

                        if collection_name == "user":
                            calculate_data = dataList

                    if calculate_data:
                        collection_name = "calculate"

                        for row in calculate_data:
                            query = {"user_name": row['user_name'], "server_id": str(row['server_id'])}
                            original_cal_data = await self.db_manager.find_documents(session, collection_name, query)
                            org_hp = -1
                            if original_cal_data:
                                row['money'] = original_cal_data[0]['money']
                                org_hp = original_cal_data[0]['hp']

                                if 'user_id' in original_cal_data[0].keys():
                                    row['user_id'] = original_cal_data[0]['user_id']

                            row['max_hp'] = row['hp']
                            if org_hp != -1:
                                row['hp'] = org_hp
                            remove_result = await self.db_manager.remove_document(session, collection_name, query)
                            update_result = await self.db_manager.create_one_document(session, collection_name, row)
                            if update_result is None:
                                await interaction.followup.send(self.messages['data_update_failure'])
                                await session.abort_transaction()
                                return

                    calculate_collection = self.db_manager.database['calculate']
                    user_data = {}
                    async for doc in calculate_collection.find({}, {"user_name": 1, "user_id": 1}):
                        if 'user_id' in doc and doc['user_id']:
                            user_data[doc['user_name']] = doc['user_id']

                    collections = await self.db_manager.database.list_collection_names()
                    if 'calculate' in collections:
                        collections.remove('calculate')

                    for collection_name in collections:
                        collection = self.db_manager.database[collection_name]
                        for user_name, user_id in user_data.items():
                            await collection.update_many(
                                {"user_name": user_name, 'server_id': server_id},
                                {"$set": {"user_id": user_id}},
                                session=session
                            )

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['data_update_from_sheet_success'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['data_update_failure'])
            return


    async def convert_numeric_strings_to_int(self, list_of_dicts : list):
        new_list_of_dicts = []
        for d in list_of_dicts:
            new_dict = {}
            for k, v in d.items():
                if k in ['channel_id', 'comu_name', "server_id"]:
                    new_dict[k] = str(v).lower()
                elif isinstance(v, str) and v.isdigit():
                    new_dict[k] = int(v)
                elif isinstance(v, int):
                    new_dict[k] = v
                else:
                    new_dict[k] = str(v).lower()
            new_list_of_dicts.append(new_dict)
        return new_list_of_dicts
    
    @app_commands.command(name="등록")
    @app_commands.describe(user_name="등록된 캐릭터 이름")
    async def register_user(self, interaction: discord.Interaction, user_name: str):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        user_id = str(interaction.user)
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴

        if not user_name:
            await interaction.followup.send(self.messages['no_args_in_register'])
            return

        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages['community_not_started'])
                        return

                    user_query = {"user_name": user_name, "server_id": server_id}
                    user_data = await self.db_manager.find_one_document(session, "user", user_query)
                    if user_data is None:
                        await interaction.followup.send(self.messages['no_user_in_db_register'])
                        await session.abort_transaction()
                        return

                    validate_data = await self.db_manager.find_one_document(session, "user", {"server_id": server_id, "user_id": user_id})
                    if validate_data is not None:
                        await interaction.followup.send(self.messages['already_registered'])
                        await session.abort_transaction()
                        return

                    update_data = {"user_id": user_id}
                    update_result = await self.db_manager.update_document(session, "user", user_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages["data_cannot_get"])
                        await session.abort_transaction()
                        return

                    update_result = await self.db_manager.update_document(session, "calculate", user_query, {"user_id": user_id, "max_hp": user_data.get('hp', 0)})
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages["data_cannot_get"])
                        await session.abort_transaction()
                        return

                    update_result = await self.db_manager.update_many_documents(session, "user_skill", user_query, {"user_id": user_id})
                    if update_result == 0:
                        await interaction.followup.send(self.messages["data_cannot_get"])
                        await session.abort_transaction()
                        return

                    calculate_collection = self.db_manager.database['calculate']
                    user_data = {}
                    async for doc in calculate_collection.find({}, {"user_name": 1, "user_id": 1}):
                        if 'user_id' in doc and doc['user_id']:
                            user_data[doc['user_name']] = doc['user_id']

                    collections = await self.db_manager.database.list_collection_names()
                    collections.remove('calculate')

                    for collection_name in collections:
                        collection = self.db_manager.database[collection_name]
                        for user_name, user_id in user_data.items():
                            await collection.update_many(
                                {"user_name": user_name, "server_id": server_id},
                                {"$set": {"user_id": user_id}},
                                session=session
                            )

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['register_success'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages["data_cannot_get"])
            return


    @register_user.autocomplete('user_name')
    async def autocomplete_user_name(self, interaction: discord.Interaction, current: str):
        # 기본 응답 목록
        default_choices = [
            app_commands.Choice(name="No matches found", value="no_matches")
        ]

        # MongoDB에서 사용자 이름 목록을 가져옴
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    user_list = await self.db_manager.find_documents(session, "user", {"server_id": server_id})
                    
                    user_names = [user['user_name'] for user in user_list if not user.get("user_id")]
        except Exception as e:
            print(f"Error fetching user names: {e}")
            return default_choices

        matches = [name for name in user_names if current.lower() in name.lower()]
        if not matches:
            return default_choices

        return [
            app_commands.Choice(name=match, value=match)
            for match in matches[:25]
        ]


    @app_commands.command(name="구매")
    @app_commands.describe(item_name="구매할 아이템의 이름", item_count="구매할 아이템의 개수 (선택 사항, 기본값: 1)")
    async def purchase(self, interaction: discord.Interaction, item_name: str, item_count: int = 1):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages['community_not_started'])
                        return

                    calculate_collection_name = "calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id}

                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    item_collection_name = "item"
                    item_query = {"item_name": item_name, "server_id": server_id}
                    item_data = await self.db_manager.find_one_document(session, item_collection_name, item_query)
                    if item_data is None:
                        await interaction.followup.send(self.messages['purchse.no_item'])
                        return

                    item_price = item_data['price'] * item_count
                    money_before = calculate_data['money']

                    if money_before < item_price:
                        await interaction.followup.send(self.messages['purchase.no_money'])
                        return

                    money_after = money_before - item_price
                    money_change = money_after - money_before

                    update_data = {"money": money_after}
                    update_result = await self.db_manager.update_document(session, calculate_collection_name, calculate_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages['purchase.error_inventory_money'])
                        await session.abort_transaction()
                        return

                    inventory_collection_name = "inventory"
                    inventory_query = {"user_id": user_id, "server_id": server_id}

                    gacha_result = list()

                    for i in range(item_count):
                        if item_data['item_type'] != 'random':
                            inventory_data = {k: v for k, v in item_data.items() if k not in ['_id']}
                            inventory_data['user_id'] = user_id
                            inventory_data['can_use'] = True
                            inventory_data['user_name'] = calculate_data['user_name']

                            inventory_result = await self.db_manager.create_one_document(session, inventory_collection_name, inventory_data)
                            if inventory_result is None:
                                await interaction.followup.send(self.messages['purchase.error_inventory_item'])
                                await session.abort_transaction()
                                return

                        else:
                            random_item_list = await self.db_manager.find_documents(session, item_collection_name, {"server_id": server_id, "item_type": {"$ne": "random"}})
                            weights = [round(0.5/len(item), 2) for item in random_item_list]
                            no_luck = 1 - sum(weights)
                            weights.append(no_luck)
                            random_item_list.append(None)

                            random_item_choice = random.choices(random_item_list, weights=weights)[0]

                            if random_item_choice is None:
                                gacha_result.append('꽝')
                                continue
                            inventory_data = {k: v for k, v in random_item_choice.items() if k not in ['_id']}
                            inventory_data['user_id'] = user_id
                            inventory_data['can_use'] = True
                            inventory_data['user_name'] = calculate_data['user_name']
                            gacha_result.append(inventory_data['item_name'])

                            inventory_result = await self.db_manager.create_one_document(session, inventory_collection_name, inventory_data)
                            if inventory_result is None:
                                await interaction.followup.send(self.messages['purchase.error_inventory_item'])
                                await session.abort_transaction()
                                return

                    slip_collection_name = "slip"
                    slip_data = dict()

                    if len(gacha_result) <= 0:
                        slip_data = {
                            "server_id": server_id,
                            "user_id": user_id,
                            "user_name": calculate_data['user_name'],
                            "money_before": money_before,
                            "money_after": money_after,
                            "money_change": money_change,
                            "description": f"구매 ({item_name} / {item_count} 개)"
                        }
                    else:
                        slip_data = {
                            "server_id": server_id,
                            "user_id": user_id,
                            "user_name": calculate_data['user_name'],
                            "money_before": money_before,
                            "money_after": money_after,
                            "money_change": money_change,
                            "description": f"구매 ({item_name} / {item_count} 개) - 가챠 결과 : {', '.join(gacha_result)}"
                        }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['purchase.error_slip'])
                        await session.abort_transaction()
                        return

                    await session.commit_transaction()
                    if len(gacha_result) <= 0:
                        await interaction.followup.send(self.messages['purchase.success'])
                    else:
                        await interaction.followup.send(self.messages['purchase.gacha_success'] + ', '.join(gacha_result))

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['purchase.error'])


    @purchase.autocomplete('item_name')
    async def autocomplete_item_name(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        
        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                item_list = await self.db_manager.find_documents(
                    session, 
                    "item", 
                    {"server_id": server_id, "item_name": {'$regex': current, "$options": "i"}}
                )
                item_names = [item['item_name'] for item in item_list]

                print(current)
                print(item_list)
                print(server_id)
        
        matches = item_names
        if not matches:
            return [app_commands.Choice(name="No matches found", value="no_matches")]

        return [
            app_commands.Choice(name=match, value=match)
            for match in matches[:25]
        ]


    @app_commands.command(name="인벤토리")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    calculate_collection_name = "calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id}
                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    send_str = self.messages['inventory.inventory_header'].format(money=calculate_data['money'])

                    inventory_collection_name = "inventory"
                    pipeline = [
                        {
                            '$match': {
                                'server_id' : server_id,
                                'user_id': user_id,
                                'can_use': True
                            }
                        },
                        {
                            '$group': {
                                '_id': {
                                    'user_id': '$user_id',
                                    'item_name': '$item_name'
                                },
                                'count': {'$sum': 1}
                            }
                        },
                        {
                            '$project': {
                                '_id': 0,
                                'user_name': '$_id.user_id',
                                'item_name': '$_id.item_name',
                                'count': 1
                            }
                        }
                    ]

                    collection = self.db_manager.database[inventory_collection_name]
                    result = collection.aggregate(pipeline, session=session)

                    summary = []
                    async for doc in result:
                        summary.append(doc)

                    for s in summary:
                        send_str += self.messages['inventory.inventory_item'].format(item_name=s['item_name'], count=s['count'])

                    send_str += self.messages['inventory.inventory_footer'].format(user_name=calculate_data['user_name'])
                    await interaction.followup.send(send_str)
        except Exception as e:
            print(e)
            await interaction.followup.send(self.messages['inventory.inventory_error'])


    @app_commands.command(name="적립")
    @app_commands.describe(reward_name="적립할 보상의 이름")
    async def accrue(self, interaction: discord.Interaction, reward_name: str, reward_count : int = 1):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            if not reward_name:
                await interaction.followup.send(self.messages["accrue.provide_reward"])
                return

            if reward_count < 1:
                await interaction.followup.send(self.messages["accrue.invalid_count"])
                return

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    calculate_collection_name = "calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id}
                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    reward_collection_name = "reward"
                    reward_query = {"reward_name": reward_name, "server_id": server_id}
                    reward_data = await self.db_manager.find_one_document(session, reward_collection_name, reward_query)
                    if reward_data is None:
                        await interaction.followup.send(self.messages['accrue.no_such_reward'])
                        return

                    reward_money = reward_data['money'] * reward_count

                    money_before = calculate_data['money']
                    money_after = money_before + reward_money
                    money_change = money_after - money_before

                    update_data = {"money": money_after}
                    update_result = await self.db_manager.update_document(session, calculate_collection_name, calculate_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages['accrue.inventory_update_error'])
                        await session.abort_transaction()
                        return

                    slip_collection_name = "slip"
                    slip_data = {
                        "server_id": server_id,
                        "user_id": user_id,
                        "user_name": calculate_data['user_name'],
                        "money_before": money_before,
                        "money_after": money_after,
                        "money_change": money_change,
                        "description": f"적립 ({reward_name} x {reward_count})"
                    }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['accrue.slip_creation_error'])
                        await session.abort_transaction()
                        return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['accrue.accrue_complete'])

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['accrue.accrue_error'])


    @accrue.autocomplete('reward_name')
    async def autocomplete_reward_name(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        
        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                reward_list = await self.db_manager.find_documents(
                    session, 
                    "reward", 
                    {"server_id": server_id, "reward_name": {'$regex': current, "$options": "i"}}
                )
                reward_names = [reward['reward_name'] for reward in reward_list]
        
        matches = reward_names
        if not matches:
            return [app_commands.Choice(name="검색이 필요합니다.", value="")]

        return [
            app_commands.Choice(name=match, value=match)
            for match in matches[:25]
        ]


    @app_commands.command(name="내정보")
    async def my_info(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    calculate_collection_name = "calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id}

                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    send_str = ""

                    for k, v in calculate_data.items():
                        if k in ['user_id', 'comu_name', 'server_id', '_id', 'user_name']:
                            continue
                        send_str += f"{k.upper()}: {str(v).upper()}\n"

                    send_str += self.messages['my_info.info_footer'].format(user_name=calculate_data['user_name'])

                    await interaction.followup.send(send_str)

        except Exception as e:
            print(e)
            await interaction.followup.send(self.messages['my_info.info_error'])


    @app_commands.command(name="배틀시작")
    @app_commands.describe(battle_name="전투의 이름", monster_list="몬스터 이름 목록 (쉼표로 구분)")
    async def start_battle(self, interaction: discord.Interaction, battle_name: str, monster_list: str = ""):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)
            monster_list = [element.strip() for element in monster_list.split(',') if element.strip() != '']
            
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    comu_name = comu_info['comu_name']

                    battle_collection_name = "battle"
                    battle_data = {"server_id": server_id, "comu_name": comu_name, "battle_name": battle_name}

                    battle_tmp = await self.db_manager.find_one_document(session, battle_collection_name, battle_data)
                    if battle_tmp is not None:
                        await interaction.followup.send(self.messages['start_battle.battle_already_done'])
                        return

                    battle_validate_data = await self.db_manager.find_one_document(session, battle_collection_name, {"server_id": server_id, "in_battle": True})
                    if battle_validate_data is not None:
                        await interaction.followup.send(self.messages['start_battle.battle_already_in_progress'])
                        return

                    monster_collection_name = "monster"
                    monster_query = {
                        "server_id": server_id,
                        "monster_name": {"$in": monster_list}
                    }

                    monster_data = await self.db_manager.find_documents(session, monster_collection_name, monster_query)
                    monster_name_database_list = [monster['monster_name'] for monster in monster_data]

                    for monster_name in monster_list:
                        if monster_name not in monster_name_database_list:
                            await interaction.followup.send(self.messages['start_battle.no_such_monster'])
                            return

                    battle_data['battle_phase'] = 1
                    battle_data['in_battle'] = True
                    battle_data['monster_list'] = monster_list
                    battle_data['turn'] = 1

                    battle_result = await self.db_manager.create_one_document(session, battle_collection_name, battle_data)
                    if battle_result is None:
                        await interaction.followup.send(self.messages['start_battle.battle_start_error'])
                        await session.abort_transaction()
                        return

                    monster_calculate_collection_name = "monster_calculate"

                    for monster in monster_data:
                        monster_calculate_data = {
                            "server_id": server_id,
                            "comu_name": comu_name,
                            "battle_name": battle_name
                        }

                        for k, v in monster.items():
                            if k in ['_id', 'server_id', 'comu_name', 'battle_name']:
                                continue

                            monster_calculate_data[k] = v

                            if k == 'hp':
                                monster_calculate_data['max_hp'] = v

                        monster_calculate_result = await self.db_manager.create_one_document(session, monster_calculate_collection_name, monster_calculate_data)
                        if monster_calculate_result is None:
                            await interaction.followup.send(self.messages['start_battle.monster_update_error'])
                            await session.abort_transaction()
                            return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['start_battle.battle_started'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['start_battle.battle_start_error'])


    @start_battle.autocomplete('monster_list')
    async def autocomplete_monster_list(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            # 쉼표로 구분하여 입력된 부분 문자열 목록을 처리
            current_monster_list = [monster.strip() for monster in current.split(',')]
            current_partial = current_monster_list[-1]

            if current_partial in current_monster_list:
                current_monster_list.remove(current_partial)

            before_monster_str = ", ".join(current_monster_list) + (", " if current_monster_list else "")

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    # 몬스터 이름 검색
                    monster_list = await self.db_manager.find_documents(session, "monster", {
                        "server_id": server_id,
                        "monster_name": {'$regex': f'^{current_partial}', "$options": "i"},
                        "monster_name": {"$nin": current_monster_list}
                    })
                    monster_names = [monster['monster_name'] for monster in monster_list]

            matches = monster_names

            if not matches:
                return [app_commands.Choice(name="검색이 오래 걸리거나 검색 기록이 없습니다.", value="")]

            choices = [
                app_commands.Choice(name=f"{before_monster_str}{match}", value=f"{before_monster_str}{match}")
                for match in matches[:25]
            ]

            return choices

        except Exception as e:
            print(e)
            return []



    @app_commands.command(name="배틀종료")
    async def end_battle(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    battle_collection_name = "battle"

                    battle_validate_data = await self.db_manager.find_one_document(session, battle_collection_name, {"server_id": server_id, "in_battle": True})
                    if battle_validate_data is None:
                        await interaction.followup.send(self.messages['end_battle.no_active_battle'])
                        return

                    battle_query = {"server_id": server_id}
                    battle_update_data = {"in_battle": False}
                    battle_update_result = await self.db_manager.update_many_documents(session, battle_collection_name, battle_query, battle_update_data)
                    if battle_update_result == 0:
                        await interaction.followup.send(self.messages['end_battle.error_ending_battle'])
                        await session.abort_transaction()
                        return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['end_battle.battle_ended'])

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['end_battle.error_ending_battle'])


    @app_commands.command(name="아이템사용")
    @app_commands.describe(item_name="사용할 아이템 이름", target="사용할 아이템의 대상")
    async def use_item(self, interaction: discord.Interaction, item_name: str, target: str):
        await interaction.response.defer()  # 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    inventory_collection_name = "inventory"
                    inventory_query = {"user_id": user_id, "server_id": server_id, "can_use": True, "item_name": item_name}
                    inventory_validation_data = await self.db_manager.find_one_document(session, inventory_collection_name, inventory_query)

                    if inventory_validation_data is None:
                        await interaction.followup.send(self.messages['use_item.no_item_in_inventory'])
                        return

                    battle_info = await self.db_manager.find_one_document(session, "battle", {"server_id": server_id, "in_battle": True})
                    if battle_info is not None and inventory_validation_data['item_type'] not in ['heal', 'buff']:
                        await interaction.followup.send(self.messages['use_item.item_not_usable_in_battle'])
                        return

                    if battle_info is not None:
                        if target is None:
                            await interaction.followup.send(self.messages['use_item.no_target_specified'])
                            return

                        target_validation = await self.db_manager.find_one_document(session, "calculate", {"server_id": server_id, "user_name": target})
                        if target_validation is None:
                            await interaction.followup.send(self.messages['use_item.invalid_target'])
                            return

                        if target_validation['hp'] <= 0:
                            await interaction.followup.send(self.messages['use_item.target_unavailable'])
                            return

                        log_data = {
                            "server_id": server_id,
                            "battle_name": battle_info['battle_name'],
                            "battle_phase": battle_info['battle_phase'],
                            "behavior": inventory_validation_data['user_name'] + f"({inventory_validation_data['user_name']})",
                            "type": inventory_validation_data['item_type'],
                            "target": target,
                            "is_calculated": False
                        }

                        if inventory_validation_data['item_type'] == "heal":
                            log_data['result'] = inventory_validation_data['formula']
                        else:
                            log_data['buff_formula'] = inventory_validation_data['formula']

                        monster_list = battle_info.get("monster_list", [])
                        if target not in monster_list:
                            log_data['target_type'] = "user"
                        else:
                            log_data['target_type'] = "monster"

                        log_result = await self.db_manager.create_one_document(session, "battle_log", log_data)
                        if log_result is None:
                            await interaction.followup.send(self.messages['use_item.log_error'])
                            await session.abort_transaction()
                            return

                    item_update_query = {'_id': inventory_validation_data['_id']}
                    item_update_data = {'can_use': False}
                    item_update_result = await self.db_manager.update_document(session, inventory_collection_name, item_update_query, item_update_data)

                    # 회복 코드 넣기
                    if inventory_validation_data['item_type'] == "heal":
                        calculate_collection_name = "calculate"
                        calculate_query = {"server_id": server_id, "user_id": {"$ne": None}, "user_name": target}
                        calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)

                        if calculate_data is None:
                            await interaction.followup.send(self.messages['use_item.calculate_error'])

                        final_hp = min(inventory_validation_data['formula'] + calculate_data['hp'], calculate_data['max_hp'])
                        calculate_update = await self.db_manager.update_document(session, calculate_collection_name, calculate_query, {'hp': final_hp})

                    slip_collection_name = "slip"
                    slip_data = {
                        "server_id": server_id,
                        "user_id": user_id,
                        "user_name": inventory_validation_data['user_name'],
                        "money_change": 0,
                        "description": f"아이템 사용 ({item_name})"
                    }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['use_item.slip_error'])
                        return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['use_item.item_used'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['use_item.error_during_use'])


    @use_item.autocomplete('item_name')
    async def item_name_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    inventory_collection_name = "inventory"
                    inventory_query = {
                        "user_id": user_id,
                        "server_id": server_id,  # server_id로 변경
                        "can_use": True,
                        "item_name": {'$regex': current, "$options": "i"}
                    }
                    inventory_data = await self.db_manager.find_documents(session, inventory_collection_name, inventory_query)

                    item_names = list(set(item["item_name"] for item in inventory_data))
                    return [app_commands.Choice(name=item_name, value=item_name) for item_name in item_names]
        except Exception as e:
            print(e)
            return []


    @use_item.autocomplete('target')
    async def item_target_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    calculate_collection_name = "calculate"
                    calculate_query = {
                        "server_id": server_id,  # server_id로 변경
                        "user_id": {"$ne": None},
                        "user_name": {'$regex': current, "$options": "i"}
                    }

                    calculate_data = await self.db_manager.find_documents(session, calculate_collection_name, calculate_query)

                    user_names = list(user["user_name"] for user in calculate_data)
                    return [app_commands.Choice(name=user_name, value=user_name) for user_name in user_names]

        except Exception as e:
            print(e)
            return []


    async def rollDice(self, dice_count, dice_face):
        dice_sum = 0
        for _ in range(dice_count):
            dice_value = random.randint(1, dice_face)
            dice_sum += dice_value
        return dice_sum

    async def calculate_skill_formula(self, behavior_info, skill_formula):
        formula_element = []
        for k, v in behavior_info.items():
            if k in ['user_id', 'comu_name', 'server_id', '_id', 'user_name']:
                continue

            if k in skill_formula and isinstance(v, int):
                dice = await self.rollDice(v, 6)
                skill_formula = skill_formula.replace(k, str(dice))
                formula_element.append(k)

        eval_result = eval(skill_formula)
        return eval_result

    async def calculate_battle_type(self, battle_type_formula, result):
        if battle_type_formula is None:
            return result

        if not isinstance(result, (int, float)):
            raise ValueError("result must be an integer or float")

        cal_battle_type_formula = battle_type_formula.lower().replace("result", str(result))
        eval_result = eval(cal_battle_type_formula)

        return eval_result

    async def do_skill(self, battle_info, target_name, target_type, behavior_calculate_info, behavior_skill_info, battle_type_formula):
        server_id = behavior_calculate_info['server_id']

        behavior_name = behavior_calculate_info.get('user_name', None)
        if behavior_name is None:
            behavior_name = behavior_calculate_info['monster_name']

        behavior_skill_name = behavior_skill_info['skill_name']
        behavior_skill_type = behavior_skill_info['type']
        behavior_skill_formula = behavior_skill_info['formula']

        result = await self.calculate_skill_formula(behavior_calculate_info, behavior_skill_formula)
        result = await self.calculate_battle_type(battle_type_formula, result)

        log_data = dict()

        if isinstance(battle_info, dict):
            battle_name = battle_info['battle_name']
            battle_phase = battle_info['battle_phase']

            log_data = {
                "server_id": server_id,
                "battle_name": battle_name,
                "battle_phase": battle_phase,
                "behavior": behavior_name,
                "skill_name": behavior_skill_name,
                "skill_scope": behavior_skill_info['scope'],
                "target": target_name,
                "target_type": target_type,
                "type": behavior_skill_type,
                "result": result,
                "is_calculated": False,
                "turn": battle_info['turn']
            }

        return log_data, result
    
    @app_commands.command(name="스킬")
    @app_commands.describe(user_skill_name="사용할 스킬의 이름", target1="스킬을 사용할 대상1", target2="스킬을 사용할 대상2", target3="스킬을 사용할 대상3", target4="스킬을 사용할 대상4", target5="스킬을 사용할 대상5")
    async def skill(self, interaction: discord.Interaction, user_skill_name: str, target1 : str, target2 : str = None, target3: str = None, target4 : str = None, target5 : str = None):
        try:
            await interaction.response.defer()  # 응답을 지연시킴
            target_list = [target for target in [target1, target2, target3, target4, target5] if target]
            messages = []  # 메시지를 저장할 리스트

            if len(target_list) < 1:
                messages.append(self.messages['skill.no_target'])
                await interaction.followup.send("\n".join(messages))
                return

            if len(target_list) != len(set(target_list)):
                messages.append(self.messages['skill.duplicate_targets'])
                await interaction.followup.send("\n".join(messages))
                return

            server_id = str(interaction.guild.id)
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        messages.append(self.messages["common.community_not_started"])
                        await interaction.followup.send("\n".join(messages))
                        return

                    battle_info = await self.db_manager.find_one_document(session, "battle", {"server_id": server_id, "in_battle": True})
                    user_skill_info = await self.db_manager.find_one_document(session, "user_skill", {"server_id": server_id, "skill_name": user_skill_name, "user_id": user_id})
                    user_calculate_info = await self.db_manager.find_one_document(session, "calculate", {"server_id": server_id, "user_id": user_id})

                    if user_calculate_info is None:
                        messages.append(self.messages['skill.not_registered'])
                        await interaction.followup.send("\n".join(messages))
                        return

                    if user_skill_info is None:
                        messages.append(self.messages['skill.skill_not_found'])
                        await interaction.followup.send("\n".join(messages))
                        return

                    if user_calculate_info['hp'] <= 0:
                        messages.append(self.messages['skill.insufficient_hp'])
                        await interaction.followup.send("\n".join(messages))
                        return

                    user_battle_type = user_calculate_info['battle_type']
                    user_name = user_calculate_info['user_name']

                    user_skill_type = user_skill_info['type']
                    user_skill_scope = user_skill_info['scope']

                    if int(user_skill_scope) < len(target_list):
                        messages.append(self.messages['skill.out_of_scope'])
                        await interaction.followup.send("\n".join(messages))
                        return

                    battle_type_info = await self.db_manager.find_one_document(session, "battle_type", {"server_id": server_id, "battle_type": user_battle_type})
                    battle_type_formula = battle_type_info[user_skill_type]

                    log_data_list = []

                    if user_skill_type != "heal" and battle_info is None:
                        messages.append(self.messages['skill.not_in_battle'])
                        await interaction.followup.send("\n".join(messages))
                        return

                    if battle_info is not None:
                        monster_list = battle_info.get("monster_list", [])
                        battle_turn = battle_info.get('turn', 1)
                        response_data = {"details": []}

                        battle_log_validation = await self.db_manager.find_one_document(session, "battle_log", {"server_id": server_id, "battle_name": battle_info['battle_name'], "battle_phase": battle_info['battle_phase'], "behavior": user_name})

                        if battle_log_validation is not None:
                            messages.append(self.messages['skill.too_fast_exhaustion'])
                            update_user_hp = await self.db_manager.update_document(session, "calculate", {"server_id": server_id, "user_id": user_id}, {"hp": 0})
                            if update_user_hp == 0:
                                messages.append(self.messages['skill.update_hp_error'])
                                await session.abort_transaction()
                            await interaction.followup.send("\n".join(messages))
                            return

                        for target in target_list:
                            if target not in monster_list:
                                target_type = "user"
                                target_info = await self.db_manager.find_one_document(session, "calculate", {"server_id": server_id, "user_name": target})
                                if target_info is None:
                                    messages.append(self.messages['skill.no_such_target'])
                                    await interaction.followup.send("\n".join(messages))
                                    return

                                if target_info['hp'] <= 0:
                                    messages.append(self.messages['skill.target_unavailable'])
                                    await interaction.followup.send("\n".join(messages))
                                    return
                            else:
                                target_type = "monster"
                                target_info = await self.db_manager.find_one_document(session, "monster_calculate", {"server_id": server_id, "monster_name": target, "battle_name": battle_info['battle_name']})
                                if target_info is None:
                                    messages.append(self.messages['skill.system_error'])
                                    await interaction.followup.send("\n".join(messages))
                                    return
                                if target_info['hp'] <= 0:
                                    messages.append(self.messages['skill.attack_sin'])
                                    await interaction.followup.send("\n".join(messages))
                                    return

                            log_dict, result = await self.do_skill(battle_info, target, target_type, user_calculate_info, user_skill_info, battle_type_formula)
                            buff_list = await self.db_manager.find_documents(session, "battle_log", {"server_id": server_id, "target": user_name, 'type': "buff", 'is_calculated': False, "battle_phase": {"$gte": battle_info['battle_phase'] - 1}})
                            if buff_list is not None and len(buff_list) > 0:
                                for buff in buff_list:
                                    if buff['type'] == "buff" and buff.get('buff_formula', None) is not None:
                                        original_result = result
                                        result = eval(buff['buff_formula'].replace("result", str(result)))
                                        response_data["details"].append(
                                            self.messages["skill.buff_applied"].format(
                                                buff_behavior=buff["behavior"], 
                                                user_name=user_name, 
                                                original_result=original_result, 
                                                result=result
                                            )
                                        )
                                        log_dict['result'] = result

                            result = round(result)
                            log_dict['result'] = result

                            response_data["details"].append(
                                self.messages["skill.skill_success"].format(
                                    skill_type=user_skill_type, 
                                    user_name=user_name, 
                                    target=target, 
                                    result=result
                                )
                            )

                            log_data_list.append(log_dict)

                        if len(monster_list) != 0:
                            monster_attacker_info_list = await self.db_manager.find_documents(session, "monster_calculate", {"server_id": server_id, "hp": {"$gt": 0}, "battle_name": battle_info['battle_name']})
                            if monster_attacker_info_list is not None and len(monster_attacker_info_list) > 0:
                                monster_attacker_info = monster_attacker_info_list[int(battle_turn % len(monster_attacker_info_list))]
                                monster_attacker = monster_attacker_info['monster_name']
                                monster_attacker_skill_list = await self.db_manager.find_documents(session, "monster_skill", {"server_id": server_id, "monster_name": monster_attacker})

                                monster_skill_info = random.choice(monster_attacker_skill_list)

                                monster_skill_scope = monster_skill_info['scope']

                                for _ in range(monster_skill_scope):
                                    monster_log, monster_result = await self.do_skill(battle_info, None, None, monster_attacker_info, monster_skill_info, None)
                                    monster_log['result'] = round(monster_log['result'])
                                    log_data_list.append(monster_log)

                        append_log_result = await self.db_manager.create_documents(session, "battle_log", log_data_list)
                        if append_log_result is None:
                            messages.append(self.messages['skill.battle_log_error'])
                            await session.abort_transaction()
                            await interaction.followup.send("\n".join(messages))
                            return

                        update_item_result = await self.db_manager.update_many_documents(session, "battle_log", {"server_id": server_id, "target": user_name, 'type': "buff", 'is_calculated': False, "battle_phase": {"$gte": battle_info['battle_phase'] - 1}}, {"is_calculated": True})

                        battle_turn_update_result = await self.db_manager.update_inc_document(session, "battle", {"server_id": server_id}, {"turn": 1})
                        if battle_turn_update_result == 0:
                            messages.append(self.messages['skill.turn_update_error'])
                            await session.abort_transaction()
                            await interaction.followup.send("\n".join(messages))
                            return

                        await session.commit_transaction()
                        messages.append("\n".join(response_data["details"]))
                        await interaction.followup.send("\n".join(messages))
                        return

                    else:
                        log_dict, result = await self.do_skill(None, target_list[0], "user", user_calculate_info, user_skill_info, battle_type_formula)
                        target_info = await self.db_manager.find_one_document(session, "calculate", {"server_id": server_id, "user_name": target_list[0]})
                        if target_info is None:
                            messages.append(self.messages['skill.no_such_target'])
                            await interaction.followup.send("\n".join(messages))
                            return

                        target_hp = min(target_info['hp'] + round(result), target_info['max_hp'])
                        target_hp = int(target_hp)
                        target_update_data = {"hp": target_hp}
                        target_update_result = await self.db_manager.update_document(session, "calculate", {"server_id": server_id, "user_name": target_list[0]}, target_update_data)
                        if target_update_result == 0:
                            messages.append(self.messages['skill.update_hp_error'])
                            await session.abort_transaction()
                            await interaction.followup.send("\n".join(messages))
                            return

                        await session.commit_transaction()
                        messages.append(self.messages['skill.skill_used'].format(target=target_list[0], hp=target_hp))
                        await interaction.followup.send("\n".join(messages))
                        return

        except Exception as e:
            print(e)
            await interaction.followup.send(self.messages['skill.error_during_attack'])


    @skill.autocomplete('user_skill_name')
    async def user_skill_name_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    user_skills = await self.db_manager.find_documents(session, "user_skill", {
                        "server_id": server_id,  # server_id로 변경
                        "user_id": user_id,
                        "skill_name": {'$regex': current, "$options": "i"}
                    })
                    
                    skill_names = [skill["skill_name"] for skill in user_skills]
                    unique_skill_names = list(set(skill_names))

                    return [app_commands.Choice(name=skill_name, value=skill_name) for skill_name in unique_skill_names if current.lower() in skill_name.lower()]
        except Exception as e:
            print(e)
            return []

    def get_all_selected_targets(self, interaction):
        # 사용자가 각 타겟에서 선택한 항목들을 통합하여 가져오는 로직
        # 예를 들어, interaction에서 모든 타겟에 대한 선택된 항목 리스트를 통합하여 반환
        selected_targets = []
        for target_name in ['target1', 'target2', 'target3', 'target4', 'target5']:
            selected_targets.extend(interaction.data.get("selected_targets", {}).get(target_name, []))
        return selected_targets

    @skill.autocomplete('target1')
    @skill.autocomplete('target2')
    @skill.autocomplete('target3')
    @skill.autocomplete('target4')
    @skill.autocomplete('target5')
    async def target_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            selected_targets = self.get_all_selected_targets(interaction)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    users = await self.db_manager.find_documents(session, "calculate", {
                        "server_id": server_id,  # server_id로 변경
                        "user_name": {'$regex': f'^{current}', "$options": "i"}
                    })

                    battle_info = await self.db_manager.find_one_document(session, "battle", {
                        "server_id": server_id,  # server_id로 변경
                        "in_battle": True
                    })

                    monsters = []
                    if battle_info:
                        monsters = battle_info.get("monster_list", [])
                        monsters = [mon for mon in monsters if mon.lower().startswith(current.lower())]

                    target_names = [user["user_name"] for user in users] + monsters
                    unique_target_names = list(set(target_names))
                    unique_target_names = [target for target in unique_target_names if target.lower() not in [t.lower() for t in selected_targets]]

                    return [app_commands.Choice(name=f'{target_name}', value=f'{target_name}') for target_name in unique_target_names]
        except Exception as e:
            print(e)
            return []


    async def log_calculate(self, battle_info: dict, log: dict, defense_log: list, attack_log: list, heal_log: list, user_hp_dict: dict, monster_hp_dict: dict):
        battle_phase = battle_info['battle_phase']

        target = log['target']
        target_type = log['target_type']
        behavior = log['behavior']
        skill_type = log['type']
        result = log['result']

        battle_log_str = ''

        if skill_type == "heal":
            log['is_calculated'] = True
            heal_log.append(log)

            original_hp = 0
            changed_hp = 0
            final_hp = 0

            if target_type == "user":
                original_hp = user_hp_dict[target]['hp']
                user_hp_dict[target]['hp'] = min(user_hp_dict[target]['hp'] + result, user_hp_dict[target]['max_hp'])
                final_hp = user_hp_dict[target]['hp']
                changed_hp = final_hp - original_hp
            else:
                original_hp = monster_hp_dict[target]['hp']
                monster_hp_dict[target]['hp'] = min(monster_hp_dict[target]['hp'] + result, monster_hp_dict[target]['max_hp'])
                final_hp = monster_hp_dict[target]['hp']
                changed_hp = final_hp - original_hp
            battle_log_str += self.messages["battle.heal"].format(skill_name=log.get("skill_name", "아이템 사용 "), behavior=behavior, target=target, result=result)
            battle_log_str += self.messages["battle.hp_change"].format(target=target, original_hp=original_hp, final_hp=final_hp, changed_hp=changed_hp)
            battle_log_str += self.messages["battle.turn_end"]

        if skill_type == "atk":
            log['is_calculated'] = True
            attack_log.append(log)

            original_hp = 0
            changed_hp = 0
            final_hp = 0

            for defense in defense_log:
                if defense['target'] == target and defense['is_calculated'] == False:
                    result = max(result - defense['result'], 0)
                    defense['is_calculated'] = True

                    defense_behavior = defense['behavior']
                    defense_target = defense['target']
                    defense_result = defense['result']
                    defense_skill_name = defense['skill_name']
                    battle_log_str += self.messages["battle.defense"].format(skill_name=defense_skill_name, behavior=defense_behavior, target=defense_target, result=-defense_result)

            if target_type == "user":
                original_hp = user_hp_dict[target]['hp']
                user_hp_dict[target]['hp'] = max(user_hp_dict[target]['hp'] - result, 0)
                final_hp = user_hp_dict[target]['hp']
                changed_hp = final_hp - original_hp
            else:
                original_hp = monster_hp_dict[target]['hp']
                monster_hp_dict[target]['hp'] = max(monster_hp_dict[target]['hp'] - result, 0)
                final_hp = monster_hp_dict[target]['hp']
                changed_hp = final_hp - original_hp

            battle_log_str += self.messages["battle.attack"].format(skill_name=log["skill_name"], behavior=behavior, target=target, result=result)
            battle_log_str += self.messages["battle.hp_change"].format(target=target, original_hp=original_hp, final_hp=final_hp, changed_hp=changed_hp)
            battle_log_str += self.messages["battle.turn_end"]

        if skill_type == "def":
            defense_log.append(log)
            if battle_phase == log['battle_phase']:
                battle_log_str += self.messages["battle.defense_deploy"].format(skill_name=log["skill_name"], behavior=behavior, target=target, result=result)
                battle_log_str += self.messages["battle.turn_end"]

        battle_log_str += '\n'

        return battle_log_str

    @app_commands.command(name="페이즈종료")
    async def end_phase(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()  # 응답을 지연시킴

            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    battle_info = await self.db_manager.find_one_document(session, "battle", {"server_id": server_id, "in_battle": True})
                    if battle_info is None:
                        await interaction.followup.send(self.messages['battle.not_in_progress'])
                        return

                    battle_name = battle_info['battle_name']
                    battle_phase = battle_info['battle_phase']
                    monster_list = battle_info['monster_list']

                    battle_log_data_list = await self.db_manager.find_documents(session, "battle_log", {"server_id": server_id, "battle_name": battle_name, "is_calculated": False, "battle_phase": {"$in": [battle_phase, battle_phase-1]}})

                    if len(battle_log_data_list) == 0:
                        await interaction.followup.send(self.messages['battle.no_logs'])
                        await session.abort_transaction()
                        return

                    defense_log = []
                    attack_log = []
                    heal_log = []

                    user_behavior_list = [log['behavior'] for log in battle_log_data_list if log['behavior'] not in monster_list]

                    user_calculate_data_list = await self.db_manager.find_documents(session, "calculate", {"server_id": server_id})
                    monster_calculate_data_list = await self.db_manager.find_documents(session, "monster_calculate", {"server_id": server_id, "battle_name": battle_name})

                    user_name_list = [user['user_name'] for user in user_calculate_data_list]

                    for mon in monster_calculate_data_list:
                        if mon['hp'] <= 0:
                            monster_calculate_data_list.remove(mon)
                            monster_list.remove(mon['monster_name'])

                    user_hp_dict = {user['user_name']: {'hp': user['hp'], 'max_hp': user['max_hp']} for user in user_calculate_data_list}
                    monster_hp_dict = {monster['monster_name']: {'hp': monster['hp'], 'max_hp': monster['max_hp']} for monster in monster_calculate_data_list}

                    battle_end_flag = False

                    user_random_list_for_monster_targeting = dict()
                    monster_random_list_for_monster_targeting = dict()

                    battle_log_str = ""

                    for log in battle_log_data_list:
                        behavior_name = log['behavior']
                        target = log['target']
                        target_type = log['target_type']
                        skill_type = log['type']

                        monster_can_list = [monster for monster in monster_list if monster_hp_dict[monster]['hp'] > 0]
                        user_can_list = [user for user in user_name_list if user_hp_dict[user]['hp'] > 0]

                        if target is None and target_type is None:
                            if len(monster_can_list) == 0 or len(user_can_list) == 0:
                                battle_end_flag = True
                                break

                            if skill_type in ("heal", "def"):

                                log['target_type'] = "monster"

                                if monster_random_list_for_monster_targeting.get(log['turn'], None) is None:
                                    monster_random_list_for_monster_targeting[log['turn']] = monster_can_list

                                if len(monster_random_list_for_monster_targeting[log['turn']]) == 0:
                                    continue

                                target_monster = random.choice(monster_random_list_for_monster_targeting[log['turn']])
                                log['target'] = target_monster
                                monster_random_list_for_monster_targeting[log['turn']].remove(target_monster)
                            else:
                                log['target_type'] = "user"

                                if user_random_list_for_monster_targeting.get(log['turn'], None) is None:
                                    user_random_list_for_monster_targeting[log['turn']] = list()

                                    for u in user_can_list:
                                        if u in user_behavior_list:
                                            user_random_list_for_monster_targeting[log['turn']].append(u)

                                if len(user_random_list_for_monster_targeting[log['turn']]) == 0:
                                    continue

                                target_user = random.choice(user_random_list_for_monster_targeting[log['turn']])
                                log['target'] = target_user
                                user_random_list_for_monster_targeting[log['turn']].remove(target_user)

                        
                        battle_log_str += await self.log_calculate(battle_info, log, defense_log, attack_log, heal_log, user_hp_dict, monster_hp_dict)

                    final_user_hp_dict = {user: user_hp_dict[user]['hp'] for user in user_name_list}
                    final_monster_hp = {monster: monster_hp_dict[monster]['hp'] for monster in monster_list}

                    final_log = defense_log + attack_log + heal_log

                    battle_log_str += self.messages["battle.remaining_defense"]

                    for defense in defense_log:
                        if defense['is_calculated'] == False and defense['battle_phase'] == battle_phase:
                            battle_log_str += self.messages["battle.remaining_defense_log"].format(target=defense["target"], result=defense["result"])

                    for log in final_log:
                        log_update_result = await self.db_manager.update_document(session, "battle_log", {"_id": log['_id']}, log)
                        if log_update_result == 0:
                            await interaction.followup.send(self.messages['battle.log_update_error'])
                            await session.abort_transaction()
                            return

                    battle_log_str += self.messages["battle.remaining_hp"]

                    phase_update_result = await self.db_manager.remove_document(session, "battle_log", {'target': None})

                    for user in set(user_name_list):
                        battle_log_str += self.messages["battle.remaining_user_hp"].format(user=user, hp=final_user_hp_dict[user])
                        user_update_result = await self.db_manager.update_document(session, "calculate", {"server_id": server_id, "user_name": user}, {"hp": final_user_hp_dict[user]})
                        if user_update_result == 0:
                            await interaction.followup.send(self.messages['battle.update_hp_error'])
                            await session.abort_transaction()
                            return

                    for monster in set(monster_list):
                        battle_log_str += self.messages["battle.remaining_monster_hp"].format(monster=monster, hp=final_monster_hp[monster])
                        monster_update_result = await self.db_manager.update_document(session, "monster_calculate", {"server_id": server_id, "monster_name": monster, "battle_name": battle_name}, {"hp": final_monster_hp[monster]})
                        if monster_update_result == 0:
                            await interaction.followup.send(self.messages['battle.update_monster_hp_error'])
                            await session.abort_transaction()
                            return

                    battle_update_result = await self.db_manager.update_inc_document(session, "battle", {"server_id": server_id, "battle_name": battle_name}, {"battle_phase": 1})
                    if battle_update_result == 0:
                        await interaction.followup.send(self.messages['battle.update_error'])
                        await session.abort_transaction()
                        return

                    if battle_end_flag:
                        battle_log_str += self.messages["battle.end"]
                    else:
                        battle_log_str += self.messages["battle.phase_end"]
                    await session.commit_transaction()

                    if len(battle_log_str) < 2000:
                        await interaction.followup.send(battle_log_str)
                    else:
                        for i in range(0, len(battle_log_str), 2000):
                            await interaction.followup.send(battle_log_str[i:i+2000])
                    return

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['battle.end_phase_error'])


    @app_commands.command(name="아이템양도")
    @app_commands.describe(item_name="양도할 아이템의 이름", target="아이템을 받을 대상")
    async def transfer_item(self, interaction: discord.Interaction, item_name: str, target: str):
        await interaction.response.defer()  # 응답 지연을 알림

        try:
            server_id = str(interaction.guild.id)
            from_user_id = str(interaction.user)  # 양도인 ID

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    # 커뮤니티 정보 확인
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    # 인벤토리에서 아이템 확인
                    inventory_item = await self.db_manager.find_one_document(
                        session,
                        "inventory",
                        {"server_id": server_id, "user_id": from_user_id, "item_name": item_name, "can_use": True}
                    )

                    if inventory_item is None:
                        await interaction.followup.send(self.messages['transfer_item.item_not_found'])
                        await session.abort_transaction()
                        return

                    # 대상 사용자 확인
                    to_user = await self.db_manager.find_one_document(
                        session,
                        "calculate",
                        {"server_id": server_id, "user_name": target}
                    )

                    if to_user is None:
                        await interaction.followup.send(self.messages['transfer_item.target_not_found'])
                        await session.abort_transaction()
                        return

                    to_user_id = to_user['user_id']  # 수령인 ID

                    # 아이템 양도: 인벤토리에서 현재 사용자 아이템 제거하고 대상 사용자에게 추가
                    inventory_update = await self.db_manager.update_document(
                        session,
                        "inventory",
                        {"_id": inventory_item["_id"]},
                        {"user_id": to_user_id, "user_name": target}
                    )

                    if inventory_update[0] == 0:
                        await interaction.followup.send(self.messages['transfer_item.transfer_failed'])
                        await session.abort_transaction()
                        return

                    # slip에 기록 남기기
                    slip_data = {
                        "server_id": server_id,
                        "from_user_id": from_user_id,  # 양도인 ID
                        "from_user_name": inventory_item['user_name'],  # 양도인 이름
                        "to_user_id": to_user_id,  # 수령인 ID
                        "to_user_name": target,  # 수령인 이름
                        "item_name": item_name,  # 양도된 아이템 이름
                        "description": f"아이템 양도: {item_name} -> {target}"
                    }

                    slip_result = await self.db_manager.create_one_document(session, "slip", slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['transfer_item.slip_error'])
                        await session.abort_transaction()
                        return

                    # 성공 메시지 전송
                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['transfer_item.success'].format(item_name=item_name, target=target))

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['transfer_item.error'])


    @transfer_item.autocomplete('item_name')
    async def autocomplete_item_name(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        user_id = str(interaction.user)

        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                items = await self.db_manager.find_documents(
                    session,
                    "inventory",
                    {"server_id": server_id, "user_id": user_id, "item_name": {'$regex': f'^{current}', "$options": "i"}, "can_use": True}
                )
                item_names = [item['item_name'] for item in items]

                return [
                    app_commands.Choice(name=item_name, value=item_name)
                    for item_name in item_names[:25]  # 최대 25개까지 자동완성 제안
                ]

    @transfer_item.autocomplete('target')
    async def autocomplete_target(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴

        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                users = await self.db_manager.find_documents(
                    session,
                    "calculate",
                    {"server_id": server_id, "user_name": {'$regex': f'^{current}', "$options": "i"}}
                )
                user_names = [user['user_name'] for user in users]

                return [
                    app_commands.Choice(name=user_name, value=user_name)
                    for user_name in user_names[:25]  # 최대 25개까지 자동완성 제안
                ]


    @app_commands.command(name="긴급탈출너구리")
    @app_commands.describe(heal_amount="회복할 HP의 양 (입력하지 않으면 최대 회복)")
    async def emergency_heal(self, interaction: discord.Interaction, heal_amount: int = None):
        await interaction.response.defer()  # 응답 지연을 알림

        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    # 커뮤니티 정보 확인
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages["common.community_not_started"])
                        return

                    # 서버의 전체 사용자 정보 조회
                    users = await self.db_manager.find_documents(session, "calculate", {"server_id": server_id})
                    if not users:
                        await interaction.followup.send(self.messages['emergency_heal.no_users_found'])
                        return

                    total_healed_users = 0
                    for user in users:
                        current_hp = user['hp']
                        max_hp = user['max_hp']

                        if heal_amount is None:
                            # 전체 회복
                            individual_heal_amount = max_hp - current_hp
                        else:
                            # 특정 양 회복
                            individual_heal_amount = min(heal_amount, max_hp - current_hp)

                        final_hp = current_hp + individual_heal_amount

                        # HP 업데이트
                        update_result = await self.db_manager.update_document(
                            session,
                            "calculate",
                            {"_id": user['_id']},
                            {"hp": final_hp}
                        )

                        if update_result[0] > 0:
                            total_healed_users += 1

                    if total_healed_users == 0:
                        await interaction.followup.send(self.messages['emergency_heal.error_during_heal'])
                        await session.abort_transaction()
                        return

                    # 성공 메시지 전송
                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['emergency_heal.success'].format(heal_amount=heal_amount if heal_amount is not None else "최대", total_healed_users=total_healed_users))

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['emergency_heal.error'])


    @app_commands.command(name="적립내역")
    async def get_slip_data(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 응답 지연을 알림

        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)  # 명령어를 친 사용자의 ID를 가져옴
            info_type = "적립"

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, server_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await interaction.followup.send(self.messages['community_not_started'])
                        return

                    calculate_collection_name = "calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id}

                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    # 기본 쿼리 조건: 서버 ID와 사용자 ID
                    query = {"server_id": server_id, "user_id": user_id, "description" : {'$regex': info_type, "$options": "i"}}

                    # 슬립 데이터 조회, 과거순으로 정렬
                    slips = await self.db_manager.find_documents(
                        session,
                        "slip",
                        query
                    )

                    if not slips:
                        await interaction.followup.send(self.messages['get_slip_data.no_data_found'])
                        return

                    # 슬립 데이터를 문자열로 변환하여 메시지로 전송
                    slip_str = ""
                    for slip in slips:
                        slip_str += f"내용: {slip['description']}\n"
                        slip_str += f"Change: {slip['money_before']} -> {slip['money_after']}  ({slip['money_change']})\n"
                        slip_str += "-" * 20 + "\n"

                    await interaction.followup.send(slip_str)

        except Exception as e:
            print(e)
            await interaction.followup.send(self.messages['get_slip_data.error'])
