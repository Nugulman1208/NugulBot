import streamlit as st
import pandas as pd
import time
import asyncio
from api_client import APIClient
from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer, UtilRenderer
import threading
import websockets
import json
import random
import datetime
import re

class MasterBattleManagement:
    def __init__(self, form_properties: str, data_editor_properties: str, message_properties: str):
        self.form_loader = PropertyLoader(form_properties)
        self.data_editor_loader = PropertyLoader(data_editor_properties)
        self.message_loader = PropertyLoader(message_properties)
        self.api_url = st.secrets["API_URL"]
        self.ws_url = st.secrets["WS_URL"]

    def get_battle_info(self):
        api = APIClient(self.api_url)
        api_path = "battle"
        comu_id = st.session_state.get('comu_id', None)
        if not comu_id:
            return None

        data_list = api.make_request(api_path, data={"comu_id": comu_id})
        if data_list and f'{api_path}_list' in data_list:
            return data_list.get(f'{api_path}_list')[0] if data_list.get(f'{api_path}_list') else None
        return None

    async def send_websocket_to_discord(self, channel_id, data):
        async with websockets.connect(self.ws_url) as websocket:
            data["channel_id"] = channel_id
            await websocket.send(json.dumps(data))

    def create_battle(self):
        st.session_state['current_page'] = "create_battle"
        comu_id = st.session_state.get('comu_id')
        server_id = st.session_state.get('server_id')

        st.title(self.message_loader.get_property("MasterBattleManagement.create_battle.title"))
        if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
            UtilRenderer.show_message(st.session_state['prior_message'], st.session_state['prior_status'])
            st.session_state['prior_message'] = None
            st.session_state['prior_status'] = None

        form_renderer = FormRenderer(self.form_loader)
        send_dict = form_renderer.render("MasterBattleManagement.create_battle.form")

        if send_dict:
            send_dict.update({"comu_id": comu_id, "server_id": server_id})
            api = APIClient(self.api_url)
            response = api.make_request("battle", data=send_dict, method='POST')
            if response:
                st.session_state.update({
                    'current_page': 'battle_monitoring',
                    'battle_id': response.get("battle_id"),
                    'prior_message': self.message_loader.get_property("common.message.success").format("배틀 시작을"),
                    'prior_status': "success",
                    'battle_room_channel_id': response.get("channel_id")
                })
                asyncio.run(self.send_websocket_to_discord(st.session_state['battle_room_channel_id'], {"action": "start_battle", "message": "배틀을 시작합니다."}))
                st.rerun()
            else:
                UtilRenderer.show_message(self.message_loader.get_property("common.message.error").format("배틀 시작을"), "error")

    def battle_monitoring(self):
        st.session_state['current_page'] = "battle_monitoring"
        battle_data = st.session_state.get('battle_data', {})
        comu_id = st.session_state.get('comu_id')
        server_id = st.session_state.get('server_id')

        st.title(self.message_loader.get_property("MasterBattleManagement.battle_monitoring.title"))
        api = APIClient(self.api_url)

        if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
            UtilRenderer.show_message(st.session_state['prior_message'], st.session_state['prior_status'])
            st.session_state['prior_message'] = None
            st.session_state['prior_status'] = None

        # 배틀 종료 버튼
        end_battle_button = st.button(self.message_loader.get_property("MasterBattleManagement.battle_monitoring.button.battle_end"), use_container_width=True, type = "primary")
        next_turn_button = st.button(self.message_loader.get_property("MasterBattleManagement.battle_monitoring.button.next_turn"), use_container_width=True)

        if next_turn_button:
            next_monster_skill_list = st.session_state['battle_monitoring.next_monster_skill']

            battle_status_data = api.make_request("battle/status", data = {"comu_id" : comu_id, "battle_id" : str(battle_data.get("_id"))})
            if battle_status_data and "battle_status_list" in battle_status_data.keys():
                battle_status_data = battle_status_data.get("battle_status_list")
            else:
                battle_status_data = list()

            result_log = list()
            for monster_skill in next_monster_skill_list:
                log = self.get_log_monster_turn(monster_skill, battle_status_data)
                if isinstance(log, dict):
                    result_log.append(log)
                elif isinstance(log, list):
                    result_log.extend(log)

            api_result = api.make_request("next", data={
                            "comu_id" : comu_id,
                            "server_id" : server_id,
                            "monster_log" : result_log,
                            "battle_id" : str(battle_data.get("_id")),
                            "battle_status_list" : battle_status_data
                        }, method='POST')

            if api_result:
                final_message = ""
                for log in result_log:
                    final_message += log.get("action_description")
                
                if api_result.get("user_description", None):
                    final_message += api_result.get("user_description", None)

                if api_result.get("monster_description", None):
                    final_message += api_result.get("monster_description", None)
                    final_message += "\n"

                if api_result.get("status_description", None):
                    final_message += api_result.get("status_description", None)
                    final_message += "\n"

                final_message += "턴을 종료 했습니다. 다음 턴으로 넘어가겠습니다."

                asyncio.run(self.send_websocket_to_discord(st.session_state['battle_room_channel_id'], {"action": "send_message", "message": final_message}))
                st.session_state['battle_monitoring.next_monster_skill'] = list()
                st.rerun()

        if end_battle_button:
            battle_id = battle_data.get('_id')
            if battle_id:
                response = api.make_request(f"battle/{battle_id}", data=battle_data, method='DELETE')
                if response:
                    asyncio.run(self.send_websocket_to_discord(st.session_state['battle_room_channel_id'], {"action": "end_battle", "message": "전투를 종료했습니다. 수고하셨습니다."}))
                    st.session_state.update({
                        'prior_message': self.message_loader.get_property("common.message.success").format("배틀 종료를"),
                        'prior_status': "success",
                        'battle_data': None,
                        'battle_room_channel_id': None,
                        'battle_log_thread': None
                    })
                    st.rerun()
                else:
                    UtilRenderer.show_message(self.message_loader.get_property("common.message.error").format("배틀 종료를"), "error")
        

        data_editor_renderer = DataEditorRenderer(self.data_editor_loader)

        tab1, tab2 = st.tabs(["몬스터 행동", "NPC 행동"])
        if 'battle_monitoring.next_monster_skill' not in st.session_state.keys():
            st.session_state['battle_monitoring.next_monster_skill'] = list()

        with tab1:
            # 몬스터 턴 전송 선택지
            selected_option = self.create_monster_turn()

            # 선택한 옵션이 있으면 상태에 추가
            if selected_option:
                st.session_state['battle_monitoring.next_monster_skill'].append(selected_option)

            idx_to_remove = None  # 삭제할 항목의 인덱스

            for idx, selected_option in enumerate(st.session_state['battle_monitoring.next_monster_skill']):
                container = st.container(border = True)
                
                with container:
                    col1, col2 = st.columns([7, 1])

                    with col1:
                        monster_name = selected_option.get("monster_name")
                        skill_name = selected_option.get("active_skill_name")
                        skill_type = selected_option.get("active_skill_type")
                        skill_scope = selected_option.get("active_skill_scope")

                        option = f"[{monster_name}][{skill_type}][{skill_scope}] {skill_name}"
                        st.write(option)

                    with col2:
                        # 삭제 버튼 생성
                        if st.button(label="삭제", key=f"delete_btn_{idx}", type="primary", use_container_width=True):
                            idx_to_remove = idx  # 삭제할 인덱스를 설정

            # 삭제 버튼이 눌린 경우 해당 항목 삭제
            if idx_to_remove is not None:
                del st.session_state['battle_monitoring.next_monster_skill'][idx_to_remove]
                st.rerun()  # 페이지를 리프레시하여 UI를 업데이트


    def create_monster_turn(self):

        battle_data = st.session_state.get('battle_data', {})
        comu_id = st.session_state.get('comu_id')
        server_id = st.session_state.get('server_id')

        api = APIClient(self.api_url)
        monster_active_list = api.make_request("monster/skill/active", data={"comu_id": comu_id})

        if monster_active_list and "monster_active_skill_list" in monster_active_list.keys():
            monster_active_list = monster_active_list.get("monster_active_skill_list")

            select_options = list()
            select_options_dict = dict()

            for skill in monster_active_list:
                if skill.get("monster_name") not in battle_data.get("monster_list"):
                    continue

                skill_id = skill.get("_id")
                monster_name = skill.get("monster_name")
                skill_name = skill.get("active_skill_name")
                skill_type = skill.get("active_skill_type")
                skill_scope = skill.get("active_skill_scope")

                option = f"[{monster_name}][{skill_type}][{skill_scope}] {skill_name}"

                select_options.append(option)
                select_options_dict[option] = skill

            if select_options and select_options_dict:
                with st.form(key="next_monster_turn"):
                    selected_option = st.selectbox("사용 스킬", select_options, key="monster_skill_select")
                    submitted = st.form_submit_button(label="추가")

                    selected_option = select_options_dict[selected_option]

                    if submitted:
                        return selected_option

    def get_log_monster_turn(self, selected_skill : dict, battle_status_data : list = []):
        battle_data = st.session_state.get('battle_data', {})
        comu_id = st.session_state.get('comu_id')
        server_id = st.session_state.get('server_id')
        channel_id = st.session_state.get('battle_room_channel_id')

        api = APIClient(self.api_url)

        target_result = selected_skill.get("active_skill_scope").lower()

        target_list = api.make_request("calculate", data={"comu_id": comu_id, "collection_type" : "monster"})
        if not target_list or "calculate_list" not in target_list.keys():
            return None

        target_list = target_list.get("calculate_list")
        behavior_dict = dict()

        for target in target_list:
            if selected_skill.get("monster_name") == target.get("monster_name"):
                behavior_dict = target

        if not behavior_dict:
            return None

        collection_type = "monster"
        target_column = "hp"
        target_standard = "min"

        if "enemy" in target_result:
            collection_type = "user"
            target_column = "hate"
            target_standard = "max"

            target_list = api.make_request("calculate", data={"comu_id": comu_id, "collection_type" : collection_type})
            if not target_list or "calculate_list" not in target_list.keys():
                return None
            target_list = target_list.get("calculate_list")
        
        
        if target_result.startswith("one"):
            standard_target_column_value = -1 * (2 ** 60)
            if target_standard == "min":
                standard_target_column_value = 2 ** 60
            standard_target_list = list()

            for target in target_list:
                if standard_target_column_value < target.get(target_column, 0):
                    if target_standard == "max" :
                        standard_target_column_value = target.get(target_column, 0)
                        standard_target_list = list()
                        standard_target_list.append(target)
                elif standard_target_column_value == target.get(target_column, 0):
                    standard_target_list.append(target)
                else:
                    if target_standard == "min":
                        standard_target_column_value = target.get(target_column, 0)
                        standard_target_list = list()
                        standard_target_list.append(target)

            if standard_target_list:
                target_result = random.choice(standard_target_list)
        
        elif "me" in target_result:
            target_result = behavior_dict


        if isinstance(target_result, dict):
            if "monster_name" in target_result.keys():
                target_name = target_result.get("monster_name")
            elif "user_name" in target_result.keys():
                target_name = target_result.get("user_name")

            dice_result, description = self.calculate_skill(selected_skill, behavior_dict, target_result, battle_status_data)

            now = datetime.datetime.now()
            now = int(now.timestamp() * 1000)

            action_target_user_id = None
            if "user_id" in target_result.keys():
                action_target_user_id = target_result.get("user_id")

            return {
                "server_id" : server_id,
                "channel_id" : channel_id,
                "comu_id" : comu_id,
                "battle_name" : battle_data.get("battle_name", ""),
                "current_turn" : battle_data.get("current_turn", 1),
                "battle_id" : str( battle_data.get("_id")),
                "action_time" : now, 
                "action_behavior" : behavior_dict.get("monster_name"),
                "action_target" : target_name,
                "action_target_user_id" : action_target_user_id,
                "action_type" : selected_skill.get("active_skill_type"),
                "action_result" : dice_result,
                "action_description" : description
            }

        else:
            return_list = list()

            target_name = str()
            target_status_list = list()

            for target in target_list:
                if "monster_name" in target.keys():
                    target_name = target.get("monster_name")
                elif "user_name" in target.keys():
                    target_name = target.get("user_name")


                dice_result, description = self.calculate_skill(selected_skill, behavior_dict, target, battle_status_data)
                now = datetime.datetime.now()
                now = int(now.timestamp() * 1000)

                action_target_user_id = None
                if "user_id" in target.keys():
                    action_target_user_id = target.get("user_id")

                return_list.append({
                    "server_id" : server_id,
                    "channel_id" : channel_id,
                    "comu_id" : comu_id,
                    "battle_name" : battle_data.get("battle_name", ""),
                    "current_turn" : battle_data.get("current_turn", 1),
                    "battle_id" : str( battle_data.get("_id")),
                    "action_time" : now, 
                    "action_behavior" : behavior_dict.get("monster_name"),
                    "action_target" : target_name,
                    "action_target_user_id" : action_target_user_id,
                    "action_type" : selected_skill.get("active_skill_type"),
                    "action_result" : dice_result,
                    "action_description" : description
                })

                target_status_list.extend(target_status_list)

            return return_list
                    

    def is_number(self, s):
        try:
            float(s)  # 숫자로 변환 시도
            return True
        except ValueError:
            return False

    def replace_formula(self, formula: str, stat: dict):
        # 공백 제거 및 소문자로 변환
        formula = formula.replace(" ", "").lower()
        
        for k, v in stat.items():
            formula = formula.replace(k.lower(), str(v))
            
        return formula

    def dice(self, dice_count, dice_face):
        dice_sum = 0
        for _ in range(dice_count):
            dice_value = random.randint(1, dice_face)
            dice_sum += dice_value
        return dice_sum

    def calculate_formula(self, formula : str, behavior_calculate : dict):
        if not formula.strip():
            formula = "0"

        if self.is_number(formula):
            return int(formula)
        formula = self.replace_formula(formula, behavior_calculate)

        # 주사위 패턴 정의 및 계산
        pattern = r"dice\((\d+),(\d+)\)"
        matches = re.findall(pattern, formula)

        for dice_count, dice_face in matches:
            # 치환된 formula 내에서 dice() 호출
            dice_result = self.dice(int(dice_count), int(dice_face))
            formula = formula.replace(f"dice({dice_count},{dice_face})", str(dice_result), 1)
        # 최종 수식을 평가하여 숫자로 반환
        result = eval(formula)
        return result

    def calculate_skill(self, active_skill_data: dict, behavior_calculate: dict, target_calculate : dict, battle_status_data : list = []):
        # formula 내 공백 제거 및 변수 치환
        formula = active_skill_data.get("active_skill_formula", "0")

        result = self.calculate_formula(formula, behavior_calculate)

        # 디스코드로 보낼 description 작성
        description = ""
        behavior_name = ""
        if "user_name" in behavior_calculate.keys():
            behavior_name = behavior_calculate.get("user_name")
        else:
            behavior_name = behavior_calculate.get("monster_name")

        target_status_list = list()
        target_name= ""
        if "user_name" in target_calculate.keys():
            target_name = target_calculate.get("user_name")
            target_status_list = [status for status in battle_status_data if status.get("status_target") == target_name]
        else:
            target_name = target_calculate.get("monster_name")
            target_status_list = [status for status in battle_status_data if status.get("status_target") == target_name]
        
        skill_name = active_skill_data.get("active_skill_name")
        skill_type = active_skill_data.get("active_skill_type").lower()

        description = ""
        if skill_type == "attack":
            # target_status : defense 반영
            for status in target_status_list:
                if result <= 0:
                    break

                if status.get("status_type") == "defense":
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
            target_calculate['hp'] = result_hp
        elif skill_type == "heal":
            description = "[{skill_name} (회복)][{behavior_name} → {target_name}] 최종 회복 : {result}\n"
            result_hp = min(target_calculate.get('max_hp'), target_calculate.get('hp') + result)
            target_calculate['hp'] = result_hp

    
        org_id_dict = {status["_id"]: status for status in battle_status_data}
        new_id_dict = {status["_id"]: status for status in target_status_list}

        org_id_dict.update(new_id_dict)
        battle_status_data = list(org_id_dict.values())

        description = description.format(skill_name = skill_name, behavior_name = behavior_name, target_name = target_name, result = str(result))
        return result, description
            

    def rendering_page(self):
        # session_state에 battle_data가 없는 경우에만 get_battle_info를 호출하여 초기화
        if not st.session_state.get("battle_data", None):
            battle_data = self.get_battle_info()
            if battle_data:
                st.session_state['battle_data'] = battle_data
                st.session_state['battle_room_channel_id'] = battle_data.get("channel_id")
            else:
                self.create_battle()
                return  # battle 생성 후 함수 종료

        self.battle_monitoring()
