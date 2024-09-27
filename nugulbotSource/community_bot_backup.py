import os
import json
import discord
from discord.ext import commands
from discord import app_commands
import shlex
from mongodb_manager import MongoDBManager
from google_sheet_manager import GoogleSheetManager

class CommunityBot(commands.Cog):
    def __init__(self, bot, mongo_uri, db_name):
        self.bot = bot
        self.db_manager = MongoDBManager(mongo_uri, db_name)
        self.sheet_manager = GoogleSheetManager()
        self.messages = self.load_messages()
        self.bot.event(self.on_command_error)  # 에러 핸들러 등록

    def load_messages(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        messages_path = os.path.join(base_dir, 'messages.json')
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.tree.sync()
        print(f'We have logged in as {self.bot.user}')
        
    @app_commands.command(name="테스트")
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message("test")

    @app_commands.command(name='커뮤시작')
    @app_commands.describe(comu_name="Community name", email="Leader email")
    async def start_community(self, ctx : discord.Interaction, comu_name : str, email : str):
        args = shlex.split(args)

        success = True
        sheet_url = ""

        channel_id = str(ctx.channel.id)
        leader_name = str(ctx.author)

        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                try:
                    collection_name = "community"
                    document = await self.db_manager.find_one_document(session, collection_name, {"channel_id": channel_id})
                    if document is not None:
                        await ctx.send(self.messages["community_already_started"])
                        await session.abort_transaction()
                        return

                    document = await self.db_manager.find_one_document(session, collection_name, {"comu_name": comu_name})
                    if document is not None:
                        await ctx.send(self.messages["community_name_conflict"])
                        await session.abort_transaction()
                        return

                    copied_sheet_id, success = await self.sheet_manager.copy_file_and_set_permission(comu_name, email)

                    if not success:
                        await ctx.send(self.messages["sheet_copy_failure"])
                        await session.abort_transaction()
                        return

                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{copied_sheet_id}"

                    modified_count, upserted_id = await self.db_manager.update_document(
                        session, collection_name, {"channel_id": channel_id}, {"channel_id": channel_id, "comu_name": comu_name, "leader_name": leader_name, "sheet_id": copied_sheet_id, "leader_email": email}
                    )

                    await session.commit_transaction()
                    await ctx.send(self.messages["community_start_success"].format(comu_name=comu_name, sheet_url=sheet_url))

                except Exception as e:
                    print(e)
                    await session.abort_transaction()
                    await ctx.send(self.messages["sheet_copy_failure"])
                    return
                
    @app_commands.command(name="커뮤정보")
    async def comu_information(self, ctx):
        try:
            channel_id = str(ctx.channel.id)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    result = await self.db_manager.get_comu_info(session, channel_id)
                    if result is None:
                        await ctx.send(self.messages["community_not_started"])
                        return;
                    
                    comu_name = result['comu_name']
                    leader_name = result['leader_name']
                    leader_email = result['leader_email']
                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{result['sheet_id']}"
                    
                    sendStr = self.messages["community_information"].format(comu_name=comu_name,
                                                                  leader_name = leader_name,
                                                                  leader_email= leader_email,
                                                                  sheet_url = sheet_url)

                    await ctx.send(sendStr)
        except Exception as e:
            print(e)
            traceback.print_exc()
            await ctx.send(self.messages["data_cannot_get"])
            
    @app_commands.command(name="데이터갱신")
    async def data_update_from_sheet(self, ctx):
        channel_id = str(ctx.channel.id)

        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, channel_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await ctx.send(self.messages["community_not_started"])
                        return

                    sheet_id = comu_info['sheet_id']
                    sheet_url = f"{GoogleSheetManager.SHEET_URL_PREFIX}{sheet_id}"
                    comu_name = comu_info['comu_name']

                    calculate_data = []
                    for sheet_name in self.sheet_manager.SHEET_NAME_LIST:
                        rowList, dataList, success = await self.sheet_manager.get_data_from_google_sheet(sheet_id, sheet_name)
                        if not success:
                            await ctx.send(self.messages['sheet_get_failure'])
                            await session.abort_transaction()
                            return

                        collection_name = sheet_name.replace("_INFORMATION", "").lower()
                        dataList = [{k.lower(): v for k, v in d.items()} for d in dataList]
                        dataList = [{'channel_id': channel_id, 'comu_name': comu_name, **d} for d in dataList]
                        dataList = await self.convert_numeric_strings_to_int(dataList)

                        delete_result = await self.db_manager.remove_document(session, collection_name, {"channel_id": channel_id})

                        update_result = await self.db_manager.create_documents(session, collection_name, dataList)
                        if update_result is None:
                            await ctx.send(self.messages['data_update_failure'])
                            await session.abort_transaction()
                            return

                        if collection_name == "user":
                            calculate_data = dataList

                    if calculate_data:
                        collection_name = "calculate"

                        for row in calculate_data:
                            query = {"user_name": row['user_name'], "channel_id": row['channel_id']}
                            original_cal_data = await self.db_manager.find_documents(session, collection_name, query)
                            if original_cal_data:
                                row['money'] = original_cal_data[0]['money']
                                if 'user_id' in original_cal_data[0].keys():
                                    row['user_id'] = original_cal_data[0]['user_id']

                            row['max_hp'] = row['hp']
                            remove_result = await self.db_manager.remove_document(session, collection_name, query)
                            update_result = await self.db_manager.create_one_document(session, collection_name, row)
                            if update_result is None:
                                await ctx.send(self.messages['data_update_failure'])
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
                                {"user_name": user_name, 'channel_id': channel_id},
                                {"$set": {"user_id": user_id}},
                                session=session
                            )

                    await session.commit_transaction()
                    await ctx.send(self.messages['data_update_from_sheet_success'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await ctx.send(self.messages['data_update_failure'])
            return

    async def convert_numeric_strings_to_int(self, list_of_dicts : list):
        new_list_of_dicts = []
        for d in list_of_dicts:
            new_dict = {}
            for k, v in d.items():
                if k in ['channel_id', 'comu_name']:
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
    async def register_user(self, ctx, user_name : str):
        user_id = str(ctx.author)
        channel_id = str(ctx.channel.id)

        if not user_name:
            await ctx.send(self.messages['no_args_in_register'])
            return

        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    comu_info = await self.db_manager.get_comu_info(session, channel_id)
                    if comu_info is None or comu_info['sheet_id'] is None:
                        await ctx.send(self.messages['community_not_started'])
                        return

                    user_query = {"user_name": user_name, "channel_id": channel_id}
                    user_data = await self.db_manager.find_one_document(session, "user", user_query)
                    if user_data is None:
                        await ctx.send(self.messages['no_user_in_db_register'])
                        await session.abort_transaction()
                        return

                    validate_data = await self.db_manager.find_one_document(session, "user", {"channel_id": channel_id, "user_id": user_id})
                    if validate_data is not None:
                        await ctx.send(messages['already_registered'])
                        await session.abort_transaction()
                        return

                    update_data = {"user_id": user_id}
                    update_result = await self.db_manager.update_document(session, "user", user_query, update_data)
                    if update_result[0] == 0:
                        await ctx.send(self.messages["data_cannot_get"])
                        await session.abort_transaction()
                        return

                    update_result = await self.db_manager.update_document(session, "calculate", user_query, {"user_id": user_id, "max_hp": user_data.get('hp', 0)})
                    if update_result[0] == 0:
                        await ctx.send(self.messages["data_cannot_get"])
                        await session.abort_transaction()
                        return

                    update_result = await self.db_manager.update_many_document(session, "user_skill", user_query, {"user_id": user_id})
                    if update_result == 0:
                        await ctx.send(self.messages["data_cannot_get"])
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
                                {"user_name": user_name, "channel_id": channel_id},
                                {"$set": {"user_id": user_id}},
                                session=session
                            )

                    await session.commit_transaction()
                    await ctx.send(self.messages['register_success'])
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await ctx.send(self.messages["data_cannot_get"])
            return
        
    @register_user.autocomplete('user_name')
    async def autocomplete_user_name(self, interaction: discord.Interaction, current: str):
        # MongoDB에서 사용자 이름 목록을 가져옴
        channel_id = str(interaction.channel_id)
        async with await interaction.client.db_manager.client.start_session() as session:
            async with session.start_transaction():
                user_list = await interaction.client.db_manager.find_documents(session, "user", {"channel_id": channel_id})
                
                user_names = [user['user_name'] for user in user_list if not user.get("user_id")]

        matches = [name for name in user_names if current.lower() in name.lower()]
        return [
            app_commands.Choice(name=match, value=match)
            for match in matches[:25]
        ]
            
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(self.messages["command_not_found"])
        else:
            await ctx.send(self.messages["unknown_error"])
            print(error)  # 디버깅을 위해 콘솔에 오류 출력
