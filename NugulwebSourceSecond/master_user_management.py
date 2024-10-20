from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer, UtilRenderer
import pandas as pd
import streamlit as st
from api_client import APIClient


class MasterUserManagement:
    def __init__(self, form_properties: str, data_editor_properties: str, message_properties : str):
        self.form_loader = PropertyLoader(form_properties)
        self.data_editor_loader = PropertyLoader(data_editor_properties)
        self.message_loader = PropertyLoader(message_properties)
        self.api_url = st.secrets["API_URL"]

    def read_delete_user_master(self):
        st.session_state['current_page'] = "read_delete_user_master"
        comu_id = st.session_state['comu_id']
        server_id = st.session_state['server_id']
        
        basic_path = "UserMasterInformation.read_delete_user_master."
        common_basic_path = "common."

        st.title(self.message_loader.get_property(basic_path + "title"))

        if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
            UtilRenderer.show_message(st.session_state['prior_message'], st.session_state['prior_status'])
            st.session_state['prior_message'] = None
            st.session_state['prior_status'] = None

        col1, col2 = st.columns([1,1])
        with col1:
            submit_button = st.button(self.message_loader.get_property(common_basic_path+"button.submit"), key="create_update_button", use_container_width=True)
        with col2:
            delete_button = st.button(self.message_loader.get_property(common_basic_path+"button.delete"), key="delete_button",use_container_width=True)

        api = APIClient(self.api_url)
        user_master_list = api.make_request("user/master", data={"comu_id": comu_id})

        selected_row = list()

        if user_master_list is not None and 'user_master_list' in user_master_list.keys():
            value_df = pd.DataFrame(user_master_list['user_master_list'])
            value_df.insert(0, 'selected', False)
        
            data_editor_renderer = DataEditorRenderer(self.data_editor_loader)

            edited_df = data_editor_renderer.render("UserMasterInformation.read_delete_user_master.table", value_df)

            selected_row = edited_df[edited_df['selected']]  # 선택된 행만 필터링
            selected_row = selected_row.to_dict(orient='records')

        if submit_button:
            if len(selected_row) == 0:
                st.session_state['current_page'] = 'create_update_user_master'
                st.session_state['selected_row'] = None
                st.rerun()
            elif len(selected_row) == 1:
                st.session_state['current_page'] = 'create_update_user_master'
                st.session_state['selected_row'] = selected_row[0]
                st.rerun()
            else:
                UtilRenderer.show_message(self.message_loader.get_property("common.message.submit_select"), "error")

        if delete_button:
            delete_flag = True
            if len(selected_row) == 0:
                UtilRenderer.show_message(self.message_loader.get_property("common.message.delete_select"), "error")
            else:
                for row in selected_row:
                    _id = row.get('_id', None)
                    if _id:
                        response = api.make_request(f"user/master/{_id}", data=row, method='DELETE')
                        if response == None:
                            delete_flag = False
                            break
                    else:
                        delete_flag = False
                
                if delete_flag:
                    st.session_state['prior_message'] = self.message_loader.get_property("common.message.success").format("유저 삭제를")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    self.message_loader.get_property("common.message.error").format("유저 삭제를")



    def create_update_user_master(self):
        st.session_state['current_page'] = "create_update_user_master"
        comu_id = st.session_state['comu_id']
        server_id = st.session_state['server_id']
        
        basic_path = "UserMasterInformation.create_update_user_master."
        common_basic_path = "common."

        st.title(self.message_loader.get_property(basic_path + "title"))

        if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
            UtilRenderer.show_message(st.session_state['prior_message'], st.session_state['prior_status'])
            st.session_state['prior_message'] = None
            st.session_state['prior_status'] = None

        col1, col2 = st.columns([6.6, 1])
        with col2:
            back_button = st.button(self.message_loader.get_property(common_basic_path+"button.back"), key="back_button")

        if back_button:
            st.session_state['current_page'] = 'read_delete_user_master'
            st.session_state['selected_row'] = None
            st.rerun()

        value_dict = st.session_state.get('selected_row') or {}
        
        form_renderer = FormRenderer(self.form_loader)
        send_dict = form_renderer.render(basic_path + "form", value_dict=value_dict)

        if send_dict:
            send_dict['comu_id'] = comu_id
            send_dict['server_id'] = server_id

            if value_dict.get('_id', None):
                send_dict['_id'] = value_dict.get("_id", "").strip()

            api = APIClient(self.api_url)

            if send_dict.get('_id', None):
                response = api.make_request(f"user/master/{send_dict['_id']}", data=send_dict, method='PUT')
                if response:
                    st.session_state['current_page'] = 'read_delete_user_master'
                    st.session_state['selected_row'] = None
                    st.session_state['prior_message'] = self.message_loader.get_property("common.message.success").format("유저 업데이트를")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    UtilRenderer.show_message(self.message_loader.get_property("common.message.error").format("유저 업데이트를"), "error")
            else:
                response = api.make_request("user/master", data=send_dict, method='POST')
                if response:
                    st.session_state['current_page'] = 'read_delete_user_master'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = self.message_loader.get_property("common.message.success").format("유저 추가를")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    UtilRenderer.show_message(self.message_loader.get_property("common.message.error").format("유저 추가를"), "error")



    def rendering_page(self, page_name: str):
        # getattr을 사용하여 안전하게 메서드 호출
        method = getattr(self, page_name, None)
        if callable(method):
            method()
        else:
            st.error(f"'{page_name}' 페이지를 찾을 수 없습니다.")

        

        
