from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer
import pandas as pd
import streamlit as st
from authentification import Authorization
from master_user_management import MasterUserManagement
from master_reward_management import MasterRewardManagement
from master_item_management import MasterItemManagement

# 메인 화면
def main():
    if 'access_token' not in st.session_state or not st.session_state['access_token']:
        st.sidebar.title("로그인 / 회원가입")

        options = ["로그인", "회원가입"]

        select = st.sidebar.radio("메뉴", options)

        if select == "회원가입":
            # Authorization 인스턴스 생성 및 페이지 렌더링
            auth_page = Authorization("nugulweb.form.properties.json", "nugulweb.table.properties.json")
            auth_page.rendering_page("sign_up")

        if select == "로그인":
            # Authorization 인스턴스 생성 및 페이지 렌더링
            auth_page = Authorization("nugulweb.form.properties.json", "nugulweb.table.properties.json")
            auth_page.rendering_page("sign_in")

    else:
        st.sidebar.title("메타 데이터 입력")

        options = ["사용자", "보상", "아이템", "패시브", "액티브", "전투보기"]

        select = st.sidebar.radio("메뉴", options)

        if select == "사용자":
            page = MasterUserManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_user_master":
                page.rendering_page("read_delete_user_master")
            else:
                page.rendering_page(st.session_state['current_page'])

        if select == "보상":
            page = MasterRewardManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_reward":
                page.rendering_page("read_delete_reward")
            else:
                page.rendering_page(st.session_state['current_page'])

        if select == "아이템":
            page = MasterItemManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_item":
                page.rendering_page("read_delete_item")
            else:
                page.rendering_page(st.session_state['current_page'])



# Streamlit 애플리케이션 시작
if __name__ == "__main__":
    main()
