from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer, UtilRenderer
import pandas as pd
import streamlit as st
from api_client import APIClient
import asyncio
import websockets
import json

class MasterBattleManagement:
    def __init__(self, form_properties: str, data_editor_properties: str, message_properties : str):
        self.form_loader = PropertyLoader(form_properties)
        self.data_editor_loader = PropertyLoader(data_editor_properties)
        self.message_loader = PropertyLoader(message_properties)
        self.api_url = st.secrets["API_URL"]
        self.ws_url = st.secrets["WS_URL"]

    def get_battle_info(self):
        api = APIClient(self.api_url)
        api_path = "battle"
        comu_id = st.session_state['comu_id']
        data_list = api.make_request(api_path, data={"comu_id": comu_id})

        if data_list is not None and f'{api_path}_list' in data_list.keys():
            data_list = data_list.get(f'{api_path}_list')
            if len(data_list) > 0:
                return data_list[0]

        return None

    async def send_websocket_to_discord(self, channel_id, data):
        async with websockets.connect(self.ws_url) as websocket:
            data["channel_id"] = channel_id
            await websocket.send(json.dumps(data))

    def create_battle(self):
        st.session_state['current_page'] = "create_battle"
        comu_id = st.session_state['comu_id']
        server_id = st.session_state['server_id']
        
        basic_path = "MasterBattleManagement.create_battle."
        common_basic_path = "common."
        api_path = "battle"

        st.title(self.message_loader.get_property(basic_path + "title"))

        if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
            UtilRenderer.show_message(st.session_state['prior_message'], st.session_state['prior_status'])
            st.session_state['prior_message'] = None
            st.session_state['prior_status'] = None

        value_dict = {}
        form_renderer = FormRenderer(self.form_loader)
        send_dict = form_renderer.render(basic_path + "form", value_dict=value_dict)

        if send_dict:
            send_dict['comu_id'] = comu_id
            send_dict['server_id'] = server_id
            api = APIClient(self.api_url)

            response = api.make_request(api_path, data=send_dict, method='POST')
            if response:
                st.session_state['current_page'] = 'battle_monitoring'
                st.session_state['battle_id'] = response.get("battle_id")
                st.session_state['prior_message'] = self.message_loader.get_property("common.message.success").format("배틀 시작을")
                st.session_state['prior_status'] = "success"
                channel_id = response.get("channel_id")
                st.session_state['battle_room_channel_id'] = channel_id
                data = {
                    "action" : "start_battle",
                    "message" : "배틀을 시작하였습니다. 건투를 빌겠습니다."
                }
                asyncio.run(self.send_websocket_to_discord(channel_id, data))
                st.rerun()
            else:
                UtilRenderer.show_message(self.message_loader.get_property("common.message.error").format("배틀 시작을"), "error")

    def battle_monitoring(self):
        st.session_state['current_page'] = "battle_monitoring"
        comu_id = st.session_state['comu_id']
        server_id = st.session_state['server_id']
        battle_data = st.session_state['battle_data']
        channel_id = st.session_state['battle_room_channel_id']
        
        basic_path = "MasterBattleManagement.battle_monitoring."
        common_basic_path = "common."
        api_path = "battle"

        st.title(self.message_loader.get_property(basic_path + "title"))

        battle_end_button = st.button(self.message_loader.get_property(basic_path+"button.battle_end"), key="battle_end_button")

        if battle_end_button:
            _id = battle_data.get('_id', None)
            api = APIClient(self.api_url)
            response = api.make_request(f"{api_path}/{_id}", data=battle_data, method='DELETE')

            if response:
                st.session_state['prior_message'] = self.message_loader.get_property("common.message.success").format("배틀 종료를")
                st.session_state['prior_status'] = "success"
                st.session_state['battle_data'] = None
                st.session_state['battle_room_channel_id'] = None
                data = {
                    "action" : "end_battle",
                    "message" : "배틀을 마쳤습니다. 수고하셨습니다."
                }
                asyncio.run(self.send_websocket_to_discord(channel_id, data))
                st.rerun()
            else:
                self.message_loader.get_property("common.message.error").format("배틀 종료를")


    def rendering_page(self):
        battle_data = self.get_battle_info()
        
        if not battle_data:
            self.create_battle()
        else:
            st.session_state['battle_data'] = battle_data
            st.session_state['battle_room_channel_id'] = battle_data.get("channel_id")

            self.battle_monitoring()




        