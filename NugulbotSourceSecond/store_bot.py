import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager
from random import randint
import random


class StoreBot(commands.Cog):
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
            

    @app_commands.command(name="적립")
    @app_commands.describe(reward_name="적립할 보상의 이름")
    async def accrue(self, interaction: discord.Interaction, reward_name: str, reward_count : int = 1):
        await interaction.response.defer()  # 즉시 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)

            if not reward_name:
                await interaction.followup.send(self.messages["StoreBot.accrue.error.args.reward_name"])
                return

            if reward_count < 1:
                await interaction.followup.send(self.messages["StoreBot.accrue.error.args.reward_count"])
                return

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    calculate_collection_name = "user_calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id, "del_flag" : False}
                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    reward_collection_name = "reward"
                    reward_query = {"reward_name": reward_name, "server_id": server_id, "del_flag" : False}
                    reward_data = await self.db_manager.find_one_document(session, reward_collection_name, reward_query)
                    if reward_data is None:
                        await interaction.followup.send(self.messages['StoreBot.accrue.error.reward.cannot_find'])
                        return

                    reward_money = reward_data['reward_money'] * reward_count

                    money_before = calculate_data.get("money", 0)
                    money_after = money_before + reward_money
                    money_change = money_after - money_before

                    update_data = {"money": money_after}
                    update_result = await self.db_manager.update_one_document(session, calculate_collection_name, calculate_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages['common.user_calculate.cannot_update'])
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
                        "description": f"[적립][{reward_name}] {money_before} → {money_after} ({reward_data['reward_money']} X {reward_count} = {money_change})"
                    }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['StoreBot.accrue.error.slip.cannot_create'])
                        await session.abort_transaction()
                        return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['common.success'].format(message = "적립을"))

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['common.catch.error'].format(error = e))


    @accrue.autocomplete('reward_name')
    async def autocomplete_reward_name(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        
        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                reward_list = await self.db_manager.find_documents(
                    session, 
                    "reward", 
                    {"server_id": server_id, "reward_name": {'$regex': current, "$options": "i"}, "del_flag" : False}
                )
                reward_names = [reward['reward_name'] for reward in reward_list]
        
        matches = reward_names
        if not matches:
            return [app_commands.Choice(name="검색이 필요합니다.", value="")]

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

            if item_count < 1:
                await interaction.followup.send(self.messages['StoreBot.purchase.error.args.item_count'])
                return

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    calculate_collection_name = "user_calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id, "del_flag" : False}

                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    item_collection_name = "item"
                    item_query = {"item_name": item_name, "server_id": server_id, "del_flag" : False}
                    item_data = await self.db_manager.find_one_document(session, item_collection_name, item_query)
                    if item_data is None:
                        await interaction.followup.send(self.messages['StoreBot.purchase.error.item.cannot_find'])
                        return

                    item_price = item_data['item_price'] * item_count
                    money_before = calculate_data['money']

                    if money_before < item_price:
                        await interaction.followup.send(self.messages['StoreBot.purchase.no_mony'])
                        return

                    money_after = money_before - item_price
                    money_change = money_after - money_before

                    update_data = {"money": money_after}
                    update_result = await self.db_manager.update_one_document(session, calculate_collection_name, calculate_query, update_data)
                    if update_result[0] == 0:
                        await interaction.followup.send(self.messages['common.user_calculate.cannot_update'])
                        await session.abort_transaction()
                        return

                    inventory_collection_name = "inventory"
                    inventory_query = {"user_id": user_id, "server_id": server_id, "del_flag" : True}

                    gacha_result = list()

                    for i in range(item_count):
                        if item_data['item_type'].casefold() != 'random'.casefold():
                            inventory_data = {k: v for k, v in item_data.items() if k not in ['_id']}
                            inventory_data['user_id'] = user_id
                            inventory_data['can_use'] = True
                            inventory_data['user_name'] = calculate_data['user_name']

                            inventory_result = await self.db_manager.create_one_document(session, inventory_collection_name, inventory_data)
                            if inventory_result is None:
                                await interaction.followup.send(self.messages['StoreBot.purchase.error.inventory.cannot_update'])
                                await session.abort_transaction()
                                return

                        else:
                            random_item_list = await self.db_manager.find_documents(session, item_collection_name, {"server_id": server_id, "item_type": {"$ne": "random"}, "del_flag" : False})
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
                                await interaction.followup.send(self.messages['StoreBot.purchase.error.inventory.cannot_update'])
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
                            "description": f"[구매] {money_before} → {money_after} ({item_name} {item_count} 개 / {money_change})"
                        }
                    else:
                        slip_data = {
                            "server_id": server_id,
                            "user_id": user_id,
                            "user_name": calculate_data['user_name'],
                            "money_before": money_before,
                            "money_after": money_after,
                            "money_change": money_change,
                            "description": f"[구매] {money_before} → {money_after} ({item_name} {item_count} 개 / {money_change}) - 가챠 결과 : {', '.join(gacha_result)}"
                        }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['StoreBot.purchase.error.slip.cannot_update'])
                        await session.abort_transaction()
                        return

                    await session.commit_transaction()
                    if len(gacha_result) <= 0:
                        await interaction.followup.send(self.messages['common.success'].format(message = "구매를"))
                    else:
                        await interaction.followup.send(self.messages['StoreBot.purchase.success.gatcha'] + ', '.join(gacha_result))

        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['common.catch.error'].format(error = e))


    @purchase.autocomplete('item_name')
    async def autocomplete_item_name(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        
        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                item_list = await self.db_manager.find_documents(
                    session, 
                    "item", 
                    {"server_id": server_id, "item_name": {'$regex': current, "$options": "i"}, "del_flag" : False}
                )
                item_names = [item['item_name'] for item in item_list]
        
        matches = item_names
        if not matches:
            return [app_commands.Choice(name="No matches found", value="no_matches")]

        return [
            app_commands.Choice(name=match, value=match)
            for match in matches[:25]
        ]