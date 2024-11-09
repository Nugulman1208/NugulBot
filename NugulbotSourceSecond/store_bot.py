import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from mongodb_manager import MongoDBManager
from random import randint
import random
import datetime
from bson import ObjectId


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

    @app_commands.command(name="아이템양도")
    @app_commands.describe(item_name="양도할 아이템의 이름", target="아이템을 받을 대상")
    async def transfer_item(self, interaction: discord.Interaction, item_name: str, target: str):
        await interaction.response.defer()  # 응답 지연을 알림

        try:
            server_id = str(interaction.guild.id)
            from_user_id = str(interaction.user)  # 양도인 ID

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():

                    from_user = await self.db_manager.find_one_document(
                        session,
                        "user_calculate",
                        {"server_id": server_id, "user_id": from_user_id, "del_flag" : False}
                    )

                    if from_user is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        await session.abort_transaction()
                        return

                    # 인벤토리에서 아이템 확인
                    inventory_item = await self.db_manager.find_one_document(
                        session,
                        "inventory",
                        {"server_id": server_id, "user_id": from_user_id, "item_name": item_name, "can_use": True, "del_flag" : False}
                    )

                    if inventory_item is None:
                        await interaction.followup.send(self.messages['StoreBot.transfer_item.error.item_not_found'])
                        await session.abort_transaction()
                        return

                    # 대상 사용자 확인
                    to_user = await self.db_manager.find_one_document(
                        session,
                        "user_calculate",
                        {"server_id": server_id, "user_name": target, "del_flag" : False}
                    )

                    if to_user is None:
                        await interaction.followup.send(self.messages['StoreBot.transfer_item.error.target_not_found'])
                        await session.abort_transaction()
                        return

                    to_user_id = to_user['user_id']  # 수령인 ID

                    # 아이템 양도: 인벤토리에서 현재 사용자 아이템 제거하고 대상 사용자에게 추가
                    inventory_update = await self.db_manager.update_one_document(
                        session,
                        "inventory",
                        {"_id": inventory_item["_id"]},
                        {"del_flag" : True}
                    )

                    if inventory_update[0] == 0:
                        await interaction.followup.send(self.messages['StoreBot.purchase.error.inventory.cannot_update'])
                        await session.abort_transaction()
                        return

                    new_inventory_data = inventory_item
                    new_inventory_data.pop("_id")
                    new_inventory_data['user_id'] = to_user['user_id']
                    new_inventory_data['can_use'] = True
                    new_inventory_data['user_name'] =  to_user['user_name']
                    new_inventory_data['del_flag'] = False

                    inventory_create = await self.db_manager.create_one_document(session, "inventory", new_inventory_data)
                    if inventory_create is None:
                        await interaction.followup.send(self.messages['StoreBot.purchase.error.inventory.cannot_update'])
                        await session.abort_transaction()
                        return

                    # slip에 기록 남기기
                    slip_data = {
                        "server_id": server_id,
                        "from_user_id": from_user['user_id'],  # 양도인 ID
                        "from_user_name": from_user['user_name'],  # 양도인 이름
                        "to_user_id": to_user_id,  # 수령인 ID
                        "to_user_name": target,  # 수령인 이름
                        "item_name": item_name,  # 양도된 아이템 이름
                        "description": f"[아이템 양도] {item_name} ({from_user['user_name']} -> {target})"
                    }

                    slip_result = await self.db_manager.create_one_document(session, "slip", slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['StoreBot.purchase.error.slip.cannot_update'])
                        await session.abort_transaction()
                        return

                    # 성공 메시지 전송
                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['StoreBot.transfer_item.success'].format(item_name=item_name, target=target))

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
                    {"server_id": server_id, "user_id": user_id, "item_name": {'$regex': f'^{current}', "$options": "i"}, "can_use": True, "del_flag" : False}
                )

                item_names = [item['item_name'] for item in items]
                item_names = list(set(item_names))

                return [
                    app_commands.Choice(name=item_name, value=item_name)
                    for item_name in item_names[:25]  # 최대 25개까지 자동완성 제안
                ]

    @transfer_item.autocomplete('target')
    async def autocomplete_target(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
        user_id = str(interaction.user)

        async with await self.db_manager.client.start_session() as session:
            async with session.start_transaction():
                users = await self.db_manager.find_documents(
                    session,
                    "user_calculate",
                    {"server_id": server_id, "user_name": {'$regex': f'^{current}', "$options": "i"}, "del_flag" : False}
                )
                user_names = [user['user_name'] for user in users if user['user_id'] != user_id]

                return [
                    app_commands.Choice(name=user_name, value=user_name)
                    for user_name in user_names[:25]  # 최대 25개까지 자동완성 제안
                ]

    @app_commands.command(name="아이템사용")
    @app_commands.describe(item_name="사용할 아이템 이름", target="사용할 아이템의 대상")
    async def use_item(self, interaction: discord.Interaction, item_name: str, target: str):
        await interaction.response.defer()  # 응답을 지연시킴
        try:
            server_id = str(interaction.guild.id)  # 서버 ID를 가져옴
            user_id = str(interaction.user)
            channel_id = str(interaction.channel.id)

            if not target or not item_name:
                await interaction.followup.send(self.messages['BattleBot.use_item.not_found_args'])
                return

            async with await self.db_manager.client.start_session() as session:
                async with session.start_transaction():
                    calculate_collection_name = "user_calculate"
                    calculate_query = {"user_id": user_id, "server_id": server_id, "del_flag" : False}
                    calculate_data = await self.db_manager.find_one_document(session, calculate_collection_name, calculate_query)
                    if calculate_data is None:
                        await interaction.followup.send(self.messages['common.not_registered_user'])
                        return

                    inventory_collection_name = "inventory"
                    inventory_query = {"user_id": user_id, "server_id": server_id, "can_use": True, "item_name": item_name}
                    inventory_validation_data = await self.db_manager.find_one_document(session, inventory_collection_name, inventory_query)

                    if inventory_validation_data is None:
                        await interaction.followup.send(self.messages['BattleBot.common.not_found_inventory'])
                        return

                    battle_info = await self.db_manager.find_one_document(session, "battle", {"server_id": server_id, "del_flag": False})

                    target_collection_name = calculate_collection_name
                    action_target_type = "party"

                    target_query = {"server_id": server_id, "user_name": target}
                    target_name_collumn = "user_name"
                    target_validation = await self.db_manager.find_one_document(session, target_collection_name, target_query)

                    if battle_info is not None:

                        
                        if target_validation is None:
                            target_collection_name = "monster_calculate"
                            action_target_type = "enemy"
                            target_name_collumn = "monster_name"
                            target_query = {"server_id" : server_id, "del_flag" : False, "battle_name" : battle_info.get("battle_name"), "monster_name" : target}

                            target_validation = await self.db_manager.find_one_document(session, target_collection_name, target_query)

                        if target_validation is None:
                            await interaction.followup.send(self.messages['BattleBot.use_item.invalid_target'])
                            return

                        now = datetime.datetime.now()
                        now = int(now.timestamp() * 1000)

                        description = f"[아이템 사용][{item_name}][{calculate_data.get('user_name')} → {target}]"

                        log_data = {
                            "server_id": server_id,
                            "channel_id" : channel_id,
                            "comu_id" : battle_info.get("comu_id"),
                            "battle_name": battle_info['battle_name'],
                            "current_turn": battle_info['current_turn'],
                            "action_behavior_name": inventory_validation_data['user_name'],
                            "action_behavior_user_id" : inventory_validation_data['user_id'],
                            "action_behavior_type" : "user",
                            "action_target_type" : action_target_type,
                            "action_target_name" : target,
                            "action_type" : f"use_item ({inventory_validation_data.get("item_type")})",
                            "action_result" : inventory_validation_data.get("item_formula", 0),
                            "action_description" :description
                        }

                        log_result = await self.db_manager.create_one_document(session, "battle_log", log_data)
                        if log_result is None:
                            await interaction.followup.send(self.messages['BattleBot.error.battle_log.create'])
                            await session.abort_transaction()
                            return
                    else:
                        if target_validation is None:
                            await interaction.followup.send(self.messages['BattleBot.use_item.invalid_target'])
                            return

                    item_update_query = {'_id': inventory_validation_data['_id']}
                    item_update_data = {'can_use': False}
                    item_update_result = await self.db_manager.update_one_document(session, inventory_collection_name, item_update_query, item_update_data)

                    # 회복 코드 넣기
                    if inventory_validation_data['item_type'] == "heal":
                        final_hp = min(int(inventory_validation_data['item_formula']) + target_validation['hp'], target_validation['max_hp'])
                        target_update = await self.db_manager.update_one_document(session, target_collection_name, target_query, {'hp': final_hp})

                    # 버프 코드 넣기
                    if inventory_validation_data['item_type'] == "buff" and battle_info:
                        status_collection_name = "battle_status"
                        battle_status_data = {
                            "server_id" : server_id,
                            "channel_id" : channel_id,
                            "comu_id" : battle_info.get("comu_id"),
                            "battle_name" : battle_info.get("battle_name"),
                            "battle_id" : ObjectId(str(battle_info.get("_id"))),
                            "status_type" : inventory_validation_data['item_type'],
                            "status_target_collection_name" : target_collection_name,
                            "status_formula" : inventory_validation_data.get("item_formula"),
                            "status_target" : target,
                            "status_end_turn" : battle_info.get("current_turn"),
                            "del_flag" : False
                        }

                        battle_status_result = await self.db_manager.create_one_document(session, status_collection_name, battle_status_data)
                        if not battle_status_result:
                            await interaction.followup.send(self.messages['BattleBot.error.battle_status.create'])
                            await session.abort_transaction()
                            return


                    slip_collection_name = "slip"
                    slip_data = {
                        "server_id": server_id,
                        "user_id": user_id,
                        "user_name": calculate_data['user_name'],
                        "description": f"[아이템사용][{item_name}] {calculate_data.get('user_name')} → {target_validation.get(target_name_collumn)}"
                    }

                    slip_result = await self.db_manager.create_one_document(session, slip_collection_name, slip_data)
                    if slip_result is None:
                        await interaction.followup.send(self.messages['StoreBot.accrue.error.slip.cannot_create'])
                        return

                    await session.commit_transaction()
                    await interaction.followup.send(self.messages['StoreBot.use_item.success'].format(item_name = item_name, target_name = target_validation.get(target_name_collumn)))
        except Exception as e:
            print(e)
            await session.abort_transaction()
            await interaction.followup.send(self.messages['common.catch.error'].format(error = e))


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
                        "del_flag" : False,
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
                    user_calculate_collection_name = "user_calculate"
                    user_calculate_query = {
                        "server_id": server_id,  # server_id로 변경
                        "user_id": {"$ne": None},
                        "user_name": {'$regex': current, "$options": "i"}
                    }

                    target_list = await self.db_manager.find_documents(session, user_calculate_collection_name, user_calculate_query)
                    target_name_list = list(user["user_name"] for user in target_list)

                    battle_info = await self.db_manager.find_one_document(session, "battle", {"server_id": server_id, "del_flag": False})

                    if battle_info:
                        monster_list = battle_info.get("monster_list", [])
                        for monster_name in monster_list:
                            target_name_list.append(monster_name)
                    
                    return [app_commands.Choice(name=target_name, value=target_name) for target_name in target_name_list]

        except Exception as e:
            print(e)
            return []
