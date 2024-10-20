# user_info_bot.py에서 UserInfoBot 클래스 수정 예시
import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager


class UserInfoBot(commands.Cog):
    def __init__(self, bot, mongo_uri, db_name):
        self.bot = bot
        self.db_manager = MongoDBManager(mongo_uri, db_name)
        self.messages = self.load_messages()

    def load_messages(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        messages_path = os.path.join(base_dir, 'messages.json')
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.bot.user}')
        try:
            # 명령어 동기화
            synced = await self.bot.tree.sync()
            print(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            print(f'Error syncing commands: {e}')

    @app_commands.command(name="등록")
    @app_commands.describe(user_name="등록된 캐릭터 이름")
    async def register_user(self, interaction: discord.Interaction, user_name: str):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        user_id = str(interaction.user)
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴

        if not user_name:
            await interaction.followup.send(self.messages['register_user.no_args'])
            return

        try:
            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    user_master_collection = "user_master"
                    user_query = {"user_name": user_name, "server_id": server_id, "del_flag" : False}

                    # db 에 user 가 있는지 확인
                    user_data = await self.db_manager.find_one_document(session, user_master_collection, user_query)
                    if user_data is None:
                        await interaction.followup.send(self.messages['common.no_user_data'])
                        await session.abort_transaction()
                        return

                    # user_id 가 등록이 되었는지 확인
                    if (user_data.get("user_id") or "").strip():
                        await interaction.followup.send(self.messages['register_user.already_registered'])
                        await session.abort_transaction()
                        return

                    # 유저 마스터 : user_data - user_id 를 더해서 업데이트
                    update_data = {"user_id": user_id}
                    update_result = await self.db_manager.update_one_document(session, user_master_collection, user_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages["common.user_master.cannot_update"])
                        await session.abort_transaction()
                        return

                    # 유저 실질 계산 테이블도 추가
                    # user_calculate
                    user_calculate_collection = "user_calculate"
                    calculate_data = user_data
                    calculate_data["user_id"] = user_id
                    calculate_data["hp"] = user_data['max_hp']
                    update_result = await self.db_manager.create_one_document(session, user_calculate_collection, calculate_data)
                    if not update_result:
                        await interaction.followup.send(self.messages["common.user_calculate.cannot_update"])
                        await session.abort_transaction()
                        return

                    # 유저 액티브 스킬들도 등록
                    skill_collection = "user_active_skill"
                    update_result = await self.db_manager.update_documents(session, skill_collection, user_query, {"user_id": user_id})

                    # 유저 패시브 스킬들도 등록
                    skill_collection = "user_passive_skill"
                    update_result = await self.db_manager.update_documents(session, skill_collection, user_query, {"user_id": user_id})

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['common.success'].format(message = "유저 등록에"))
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages["common.catch.error"].format(error = e))
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
                    user_list = await self.db_manager.find_documents(session, "user_master", {"server_id": server_id, "del_flag" : False})
                    
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

    @app_commands.command(name="내정보")
    async def my_info(self, interaction: discord.Interaction):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    user_calculate_collection = "user_calculate"
                    user_query = {"user_id": user_id, "server_id": server_id, "del_flag" : False}

                    user_data = await self.db_manager.find_one_document(session, user_calculate_collection, user_query)
                    if user_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    send_str = ""

                    for k, v in user_data.items():
                        if k in ['user_id', 'comu_id', 'server_id', '_id', "user_name", "del_flag"]:
                            continue
                        send_str += f"{k.upper()}: {str(v).upper()}\n"

                    send_str += self.messages['my_info.info_footer'].format(user_name=user_data['user_name'])

                    await interaction.followup.send(send_str)

        except Exception as e:
            print(e)
            await interaction.followup.send(self.messages['my_info.info_error'].format(error=e))