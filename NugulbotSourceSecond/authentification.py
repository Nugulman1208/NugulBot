from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer
import pandas as pd
import streamlit as st
from api_client import APIClient

class Authorization:
    def __init__(self, form_properties: str, data_editor_properties: str):
        self.form_loader = PropertyLoader(form_properties)
        self.data_editor_loader = PropertyLoader(data_editor_properties)
        self.api_url = st.secrets["API_URL"]

    def sign_up(self):
        st.session_state['current_page'] = "sign_up"

        form_renderer = FormRenderer(self.form_loader)
        value_dict = dict()
        send_list = form_renderer.render("Authorization.sign_up.form", value_dict=value_dict)
        
        if send_list:
            api = APIClient(self.api_url)
            result = api.make_request("sign_up", data=send_list, method='POST')

            # 결과에 따라 메시지 출력
            if result:
                st.success(result.get("message"))
            else:
                st.error("회원가입 중 오류가 발생했습니다. 아이디가 중복되었을 수 있습니다.")

    def sign_in(self):
        st.session_state['current_page'] = "sign_in"

        form_renderer = FormRenderer(self.form_loader)
        value_dict = dict()
        send_list = form_renderer.render("Authorization.sign_in.form", value_dict=value_dict)

        if send_list:
            api = APIClient(self.api_url)
            result = api.make_request("sign_in", data=send_list, method='POST')

            # 결과에 따라 메시지 출력
            if result:
                st.success("로그인에 성공했습니다!")
                # 로그인에 성공하면 토큰을 세션 상태에 저장
                st.session_state['access_token'] = result.get("access_token")
                st.session_state['comu_id'] = result.get("comu_id")
                st.session_state['server_id'] = result.get("server_id")
                st.rerun()

            else:
                st.error("로그인에 실패했습니다. 아이디와 비밀번호를 확인하세요.")

    def rendering_page(self, page_name: str):
        # getattr을 사용하여 안전하게 메서드 호출
        method = getattr(self, page_name, None)
        if callable(method):
            method()
        else:
            st.error(f"'{page_name}' 페이지를 찾을 수 없습니다.")
