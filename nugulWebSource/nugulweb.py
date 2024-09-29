import streamlit as st
import requests
import os
import json
import pandas as pd 
import base64

API_URL = "http://localhost:8000"

def load_properties(json_name: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    messages_path = os.path.join(base_dir, json_name)
    with open(messages_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_properties(message: dict, path: str):
    message_key = path.split('.')
    result = message

    for k in message_key:
        if isinstance(result, dict) and k in result:
            result = result[k]
        else:
            return None

    return result

def rendering_form(message : dict, form_properties : dict,   path : str, send_list : dict, value_dict : dict = {}):
    key_list = path.split('.')
    result = form_properties

    for k in key_list:
        if isinstance(result, dict) and k in result:
            result = result[k]
        else:
            return None

    if isinstance(result, dict) == False:
        return None

    send_list = dict()
    for item_name in result:
        label = get_properties(message, path+"."+item_name)
        properties = result[item_name]
        value = value_dict.get(item_name) or None

        if properties['input_type'] == 'text_input':
            send_list[item_name] = st.text_input(label, value = value)
        if properties['input_type'] == 'checkbox':
            send_list[item_name] = st.checkbox(label, value = value)
        if properties['input_type'] == "file_uploader":
            file_type = properties.get('file_type', ["png", "jpg"])
            accept_multiple_files = properties.get("accept_multiple_files", False)

            if value == None:
                send_list[item_name] = st.file_uploader(label, type = file_type, accept_multiple_files = accept_multiple_files)

        if properties['input_type'] == "selectbox":
            item_type_options = properties.get("item_type_options", [])

            send_list[item_name] = st.selectbox(label, item_type_options,  index=item_type_options.index(value) if value in item_type_options else 0)
        
        if properties['input_type'] == "number_input":
            min_value = properties.get("number_input", 0)
            send_list[item_name] = st.number_input(label, min_value = min_value, value =value)

        if properties['input_type'] == "text_area":
            send_list[item_name] = st.text_area(label, value = value)
    
    return send_list
    
def validate(form_properties : dict, path : str, send_dict : dict):
    key_list = path.split('.')
    result = form_properties

    for k in key_list:
        if isinstance(result, dict) and k in result:
            result = result[k]
        else:
            return None

    if isinstance(result, dict) == False:
        return None

    for item_name in result:
        required = result.get(item_name, {}).get("required", False)
        if required:
            value = send_dict.get(item_name, "")
            if value == None:
                return False
            if isinstance(value, str) and str(value).strip() == "":
                return False

    return True

@st.dialog("Result")
def show_message(message, msg_type):
    if msg_type == "success":
        st.success(message)
    elif msg_type == "error":
        st.error(message)

message = load_properties("nugulweb.message.json")
form_properties = load_properties("nugulweb.form.properties.json")

# 회원가입 페이지
def register():
    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    st.title(get_properties(message, "register.title"))
    username = st.text_input(get_properties(message, "register.form.username"))
    password = st.text_input(get_properties(message, "register.form.password"), type="password")
    is_admin = st.checkbox(get_properties(message, "register.form.is_admin"))
    comu_id = st.text_input(get_properties(message, "register.form.comu_id"))
    photo = st.file_uploader(get_properties(message, "register.form.photo"), type=["png", "jpg"], accept_multiple_files=False)
    

    if st.button(get_properties(message, 'register.button.submit')):
        photo_result = None
        if photo:
            photo_bytes = photo.read()
            photo_result = f"data:image/png;base64,{base64.b64encode(photo_bytes).decode()}"
        response = requests.post(f"{API_URL}/register", json={
            "username": username,
            "password": password,
            "is_admin": is_admin,
            "comu_id": comu_id,
            "photo": photo_result if photo_result else None
        })
        if response.status_code != 200:
            st.session_state['prior_message'] = "회원가입에 실패했습니다"
            st.session_state['prior_status'] = "error"
            st.rerun()
        else:
            st.session_state['prior_message'] = "회원가입에 성공했습니다"
            st.session_state['prior_status'] = "success"
            st.rerun()

# 로그인 페이지
def login():
    st.title(get_properties(message, 'login.title'))
    username = st.text_input(get_properties(message, 'login.form.username'))
    password = st.text_input(get_properties(message, 'login.form.password'), type="password")
    comu_id = st.text_input(get_properties(message, 'login.form.comu_id'))

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None
    
    if st.button(get_properties(message, 'login.button.submit')):
        response = requests.post(f"{API_URL}/login", json={
            "username": username,
            "password": password,
            "comu_id": comu_id
        })
        if response.status_code == 200:
            st.success("Login successful")
            token_data = response.json()
            st.session_state['access_token'] = token_data['access_token']
            st.session_state['is_admin'] = token_data['is_admin']
            st.session_state['comu_id'] = comu_id
            st.session_state['login_status'] = True  # 로그인 상태 저장
            st.session_state['current_page'] = 'item_crud'  # 현재 페이지 설정
            st.rerun()  # 페이지 리프레시
        else:
            st.error("Invalid username or password")

# API 요청 처리 함수
def make_api_request(endpoint, data=None, method='GET'):
    headers = {}
    
    # 세션 상태에서 토큰 가져오기
    if 'access_token' in st.session_state:
        headers['Authorization'] = f"Bearer {st.session_state['access_token']}"
    
    # API 요청 처리
    if method == 'POST':
        response = requests.post(f"{API_URL}/{endpoint}", json=data, headers=headers)
    elif method == 'GET':
        response = requests.get(f"{API_URL}/{endpoint}", headers=headers, params=data)
    elif method == 'PUT':
        response = requests.put(f"{API_URL}/{endpoint}", json=data, headers=headers)
    elif method == 'DELETE':
        response = requests.delete(f"{API_URL}/{endpoint}", headers=headers, json=data)
    
    # 토큰 유효시간 만료 처리
    if response.status_code == 401:
        st.error(get_properties(message, 'error.make_api_request.401'))
        st.session_state.clear()  # 모든 세션 상태 제거
        st.session_state['current_page'] = 'login'  # 로그인 페이지로 돌아가기
        return None  # None을 반환하여 로그인 페이지로 돌아가게 합니다.

    elif response.status_code != 200:
        return None
    
    # 요청이 성공하면 JSON 응답 반환
    return response.json()


# 아이템 CRUD 페이지 (관리자 전용)
def item_crud():
    st.title(get_properties(message, 'admin.item_crud.title'))

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 아이템 목록 보기
    comu_id = st.session_state.get('comu_id')
    items = make_api_request("items", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청

    if items is not None and 'items' in items.keys():
        items_df = pd.DataFrame(items['items'])

        items_df.insert(0, 'selected', False)

        col1, col2 = st.columns([1,1])
        with col1:
            submit_button = st.button("CREATE/UPDATE", key="create_update_button", use_container_width=True)
        with col2:
            delete_button = st.button("DELETE", key="delete_button",use_container_width=True)
            
        edited_df = st.data_editor(items_df, use_container_width=True, hide_index =True, column_config = {
            "_id" : None,
            "item_name" : get_properties(message, "admin.item_crud.data_editor.item_name"),
            "item_description" : get_properties(message, "admin.item_crud.data_editor.item_description"),
            "item_price" : get_properties(message, "admin.item_crud.data_editor.item_price"),
            "item_type" : get_properties(message, "admin.item_crud.data_editor.item_type"),
            "item_photo" : st.column_config.ImageColumn(label=get_properties(message, "admin.item_crud.data_editor.item_photo"),width="small", help=None),
            "comu_id" : None,
            "selected": st.column_config.CheckboxColumn(label=get_properties(message, "admin.item_crud.data_editor.selected"), width="small")  # 체크박스 컬럼
        }, disabled = ['_id', "item_name", "item_description", "item_price", "item_type", "item_photo", "comu_id"])

        selected_items = edited_df[edited_df['selected']]  # 선택된 행만 필터링
        selected_items = selected_items.to_dict(orient='records')

        if submit_button:
            if len(selected_items) == 0:
                st.session_state['current_page'] = 'create_update_item'
                st.session_state['selected_item'] = None
                st.rerun()
            elif len(selected_items) == 1:
                st.session_state['current_page'] = 'create_update_item'
                st.session_state['selected_item'] = selected_items[0]
                st.rerun()
            else:
                st.error(get_properties(message, "error.admin.item_crud.selected"))

        if delete_button:
            delete_flag = True
            if len(selected_items) == 0:
                show_message(get_properties(message, "error.admin.item_crud.delete_selected"), "error")
            else:
                for item in selected_items:
                    _id = item.get('_id', None)
                    if _id:
                        response = make_api_request(f"items/{_id}", data=item, method='DELETE')
                        if response == None:
                            delete_flag = False
                            break
                    else:
                        delete_flag = False
                
                if delete_flag:
                    st.session_state['prior_message'] = get_properties(message, "success.admin.item_crud.delete")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error.admin.item_crud.delete"), "error")
            



def create_update_item():
    # 새 아이템 추가
    item_selected = st.session_state.get('selected_item') or {}

    col1, col2 = st.columns([6.6, 1])
    with col1:
        if item_selected == {}:
            st.subheader(get_properties(message, 'admin.item_crud.subtitle.add_item'))
        else:
            st.subheader(get_properties(message, 'admin.item_crud.subtitle.update_item'))
    with col2:
        back_button = st.button(get_properties(message, 'common.button.back'), key="back_button")
        

    send_dict = rendering_form(message, form_properties, "admin.item_crud.form", {}, item_selected)
    comu_id = st.session_state.get('comu_id') or None
        
    send_dict['comu_id'] = comu_id
    if item_selected.get("_id", None):
        send_dict['_id'] = item_selected.get("_id", "").strip()
    

    submit_button = st.button("submit", key="submit_button", use_container_width=True)

    if back_button:
        st.session_state['current_page'] = 'item_crud'
        st.session_state['selected_item'] = None
        st.rerun()

    if submit_button:
        if validate(form_properties, "admin.item_crud.form", send_dict) == False:
            st.error(get_properties(message, "error.admin.item_crud.required"))
        else:
            if send_dict.get("item_photo", None):
                photo_bytes = send_dict["item_photo"].read()
                photo_b64 = f"data:image/png;base64,{base64.b64encode(photo_bytes).decode()}"
                send_dict["item_photo"] = photo_b64
            elif item_selected.get("item_photo", None):
                send_dict['item_photo'] = item_selected.get("item_photo")

            if send_dict.get('_id', None):
                response = make_api_request(f"items/{send_dict['_id']}", data=send_dict, method='PUT')
                if response:
                    st.session_state['current_page'] = 'item_crud'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success.admin.item_crud.update")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error.admin.item_crud.update"), "error")
            else:
                response = make_api_request("items", data=send_dict, method='POST')
                if response:
                    st.session_state['current_page'] = 'item_crud'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success.admin.item_crud.create")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error.admin.item_crud.create"), "error")
            

def buy_item():
    st.title("아이템 구매")

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 아이템 목록 보기
    comu_id = st.session_state.get('comu_id')
    items = make_api_request("items", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청
    items = items['items']

    cols = st.columns(3)
    for i in range(len(items)):
        item = items[i]
        with cols[i % 3]:
            with st.expander(label=item['item_name'], expanded=True):
                st.image(item["item_photo"])
                buy_button = st.button(label="아이템 구매", key=i, use_container_width=True)

def create_update_reward():
    reward_selected = st.session_state.get('selected_reward') or {}

    col1, col2 = st.columns([6.6, 1])
    with col1:
        if reward_selected == {}:
            st.subheader(get_properties(message, 'admin.create_update_reward.subtitle.create_item'))
        else:
            st.subheader(get_properties(message, 'admin.create_update_reward.subtitle.update_item'))
    with col2:
        back_button = st.button(get_properties(message, 'common.button.back'), key="back_button")

    send_dict = rendering_form(message, form_properties, "admin.create_update_reward.form", {}, reward_selected)



# 메인 화면
def main():
    st.sidebar.title(get_properties(message, 'main.sidebar.title'))

    menu_title_mapping = {
        "login" : get_properties(message, 'login.title'),
        "register" : get_properties(message, 'register.title')
    }

    if 'login_status' not in st.session_state or not st.session_state['login_status']:

        options = [get_properties(message, 'login.title'), get_properties(message, 'register.title')]

        options = st.sidebar.radio(get_properties(message, 'main.sidebar.radio.title'), options)
        
        if options == get_properties(message, 'login.title'):
            login()
        elif options == get_properties(message, 'register.title'):
            register()
    elif st.session_state.get("is_admin", False) == True:
        options = st.sidebar.radio(get_properties(message, 'main.sidebar.radio.title'), 
                                    [get_properties(message, 'admin.item_crud.title'), get_properties(message, 'admin.create_update_reward.title')])
        
        if options == get_properties(message, 'admin.item_crud.title'):
            if st.session_state['current_page'] != 'create_update_item':
                item_crud()  # 로그인 후 아이템 CRUD 페이지 표시
            else:
                create_update_item()
        elif options == get_properties(message, 'admin.create_update_reward.title'):
            create_update_reward()
    else:
        options = st.sidebar.radio(get_properties(message, 'main.sidebar.radio.title'), 
                                    ["아이템 구매"])
        
        if options == "아이템 구매":
            buy_item()
        
if __name__ == "__main__":
    main()
