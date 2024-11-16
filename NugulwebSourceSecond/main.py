from easy_streamlit_framework import PropertyLoader, DataEditorRenderer, FormRenderer
import pandas as pd
import streamlit as st
from authentification import Authorization
from master_user_management import MasterUserManagement
from master_reward_management import MasterRewardManagement
from master_item_management import MasterItemManagement
from master_user_active_skill_management import MasterUserActiveSkillManagement
from master_monster_management import MasterMonsterManagement
from master_monster_active_skill_management import MasterMonsterActiveSkillManagement
from master_battle_management import MasterBattleManagement

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

        user_active_skill_option = "유저 액티브 스킬"
        monster_option = "몬스터 정보"
        monster_active_skill_option = "몬스터 액티브 스킬"
        battle_option = "전투보기"

        options = ["사용자", "보상", "아이템", user_active_skill_option, monster_option, monster_active_skill_option, battle_option]

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

        if select == user_active_skill_option:
            page = MasterUserActiveSkillManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_user_active_skill":
                page.rendering_page("read_delete_user_active_skill")
            else:
                page.rendering_page(st.session_state['current_page'])

        if select == monster_option:
            page = MasterMonsterManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_monster":
                page.rendering_page("read_delete_monster")
            else:
                page.rendering_page(st.session_state['current_page'])

        if select == monster_active_skill_option:
            page = MasterMonsterActiveSkillManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")

            if st.session_state['current_page'] != "create_update_monster_active_skill":
                page.rendering_page("read_delete_monster_active_skill")
            else:
                page.rendering_page(st.session_state['current_page'])

        if select == battle_option:
            page = MasterBattleManagement("nugulweb.form.properties.json", "nugulweb.table.properties.json", "nugulweb.message.properties.json")
            page.rendering_page()



# Streamlit 애플리케이션 시작
if __name__ == "__main__":
    main()
