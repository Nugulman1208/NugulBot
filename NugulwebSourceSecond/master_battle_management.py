import streamlit as st
import pandas as pd
import time
import asyncio
from api_client import APIClient
from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer, UtilRenderer
import threading
import websockets
import json

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

        tab1, tab2 = st.tabs(["몬스터 턴 전송", "도움 턴"])
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
                        option = f"[{monster_name}][{skill_type}] {skill_name}"
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
        st.session_state['current_page'] = "battle_monitoring"

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
                skill_id = skill.get("_id")
                monster_name = skill.get("monster_name")
                skill_name = skill.get("active_skill_name")
                skill_type = skill.get("active_skill_type")

                option = f"[{monster_name}][{skill_type}] {skill_name}"

                select_options.append(option)
                select_options_dict[option] = skill

            if select_options and select_options_dict:
                with st.form(key="next_monster_turn"):
                    selected_option = st.selectbox("사용 스킬", select_options, key="monster_skill_select")
                    submitted = st.form_submit_button(label="추가")

                    selected_option = select_options_dict[selected_option]

                    if submitted:
                        return selected_option


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
