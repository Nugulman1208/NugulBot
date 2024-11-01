import streamlit as st
import requests
import os
import json
import pandas as pd 
import base64


API_URL = st.secrets["API_URL"]


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

message = load_properties("nugulweb.message.json")
form_properties = load_properties("nugulweb.form.properties.json")
table_properties = load_properties("nugulweb.table.properties.json")

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

    with st.form(key="form"):
        for item_name in result:

            label = get_properties(message, path+"."+item_name) or item_name
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
                min_value = properties.get("min_value", 0)
                max_value = properties.get("max_value", None)
                send_list[item_name] = st.number_input(label, min_value = min_value, value =value, max_value = max_value)

            if properties['input_type'] == "text_area":
                send_list[item_name] = st.text_area(label, value = value)
        send_list['submit_button'] = st.form_submit_button(use_container_width=True)
    
    return send_list

def rendering_data_editor(message : dict, table_properties : dict,  path : str, value_df : pd.DataFrame):
    key_list = path.split('.')
    tp = table_properties

    for k in key_list:
        if isinstance(tp, dict) and k in tp:
            tp = tp[k]
        else:
            return None

    if isinstance(tp, dict) == False:
        return None

    column_config = dict()
    show_col_list = list()

    for item_name in tp:
        show_col_list.append(item_name)

        label = get_properties(message, path+"."+item_name)
        properties = tp[item_name]
        col_type = properties.get('column_type', "text")

        width = properties.get('width', "small")
        if width not in ["small", "medium", "large"]:
            width  = "small"
        required = properties.get('required', False)
        if not isinstance(required, bool):
            required = False

        disabled = properties.get('disabled', True)
        if not isinstance(disabled, bool):
            disabled = True

        if col_type == "text":
            column_config[item_name] = st.column_config.TextColumn(
                label = label,
                width = width,
                required = required,
                disabled = disabled
            )
        elif col_type == "number":
            max_value = properties.get('max_value', None)
            min_value = properties.get('min_value', None)

            if not isinstance(max_value, int) or max_value is not None:
                max_value = None
            if not isinstance(min_value, int) or min_value is not None:
                min_value = 0

            column_config[item_name] = st.column_config.NumberColumn(
                label = label,
                width = width,
                required = required,
                disabled = disabled,
                min_value = min_value,
                max_value = max_value
            )
        elif col_type == "checkbox":
            column_config[item_name] = st.column_config.CheckboxColumn(
                label = label,
                width = width,
                required = required,
                disabled = disabled
            )
        elif col_type == "photo":
            column_config[item_name] = st.column_config.ImageColumn(label=label,width=width),
    for none_col in value_df.columns:
         if none_col not in show_col_list:
            column_config[none_col] = None

    edited_df = st.data_editor(
        value_df,
        use_container_width=True,
        hide_index =True, 
        column_config = column_config
    )

    return edited_df


    
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
        min_value =  result.get(item_name, {}).get("min_value", None)
        max_value =  result.get(item_name, {}).get("max_value", None)

        if required:
            value = send_dict.get(item_name, "")
            if value == None:
                return False
            if isinstance(value, str) and str(value).strip() == "":
                return False
            elif isinstance(value, int):
                if min_value and value < min_value:
                    return False
                if max_value and value > max_value:
                    return False


    return True

@st.dialog("Result")
def show_message(message, msg_type):
    if msg_type == "success":
        st.success(message)
    elif msg_type == "error":
        st.error(message)


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
            st.session_state['username'] = username
            st.session_state['login_status'] = True  # 로그인 상태 저장
            st.session_state['current_page'] = 'item_crud'  # 현재 페이지 설정
            st.rerun()  # 페이지 리프레시
        else:
            st.error("Invalid username or password")

def logout():
    st.session_state.clear()  # 모든 세션 상태 제거
    st.session_state['current_page'] = 'login'  # 로그인 페이지로 돌아가기
    st.rerun()

# API 요청 처리 함수
def make_api_request(endpoint, data=None, method='GET'):
    headers = {}

    data = {key: value for key, value in data.items() if key != "submit_button"}
    
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
    st.session_state['current_page'] = 'item_crud'
    st.title(get_properties(message, 'admin.item_crud.title'))

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 아이템 목록 보기
    comu_id = st.session_state.get('comu_id')
    items = make_api_request("items", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청

    col1, col2 = st.columns([1,1])
    with col1:
        submit_button = st.button("CREATE/UPDATE", key="create_update_button", use_container_width=True)
    with col2:
        delete_button = st.button("DELETE", key="delete_button",use_container_width=True)

    if items is not None and 'items' in items.keys():
        items_df = pd.DataFrame(items['items'])

        items_df.insert(0, 'selected', False)

        
            
        edited_df = st.data_editor(items_df, use_container_width=True, hide_index =True, column_config = {
            "_id" : None,
            "item_name" : get_properties(message, "admin.item_crud.data_editor.item_name"),
            "item_description" : get_properties(message, "admin.item_crud.data_editor.item_description"),
            "item_price" : get_properties(message, "admin.item_crud.data_editor.item_price"),
            "item_type" : get_properties(message, "admin.item_crud.data_editor.item_type"),
            "item_photo" : st.column_config.ImageColumn(label=get_properties(message, "admin.item_crud.data_editor.item_photo"),width="small", help=None),
            "comu_id" : None,
            "selected": st.column_config.CheckboxColumn(label=get_properties(message, "admin.item_crud.data_editor.selected"), width="small"),  # 체크박스 컬럼
            "item_formula" : get_properties(message, "admin.item_crud.data_editor.item_formula"),
        }, disabled = ['_id', "item_name", "item_description", "item_price", "item_type", "item_photo", "comu_id", "item_formula"])

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
    st.session_state['current_page'] = 'create_update_item'
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
    

    submit_button = send_dict['submit_button']

    if back_button:
        st.session_state['current_page'] = 'item_crud'
        st.session_state['selected_item'] = None
        st.rerun()

    if submit_button:
        if validate(form_properties, "admin.item_crud.form", send_dict) == False:
            st.error(get_properties(message, "error.admin.item_crud.required"))
        elif send_dict.get('item_formula', '') and send_dict.get('item_formula', '').strip() and not send_dict['item_formula'].startswith('RESULT'):
            st.error(get_properties(message, "error.admin.item_crud.item_formula"))
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

@st.dialog(get_properties(message, 'user.buy_item.title'))
def buy_item_popup(item : dict):
    send_dict = dict()

    send_dict = rendering_form(message, form_properties, "user.buy_item.form", send_dict)
    comu_id = st.session_state.get('comu_id')
    username = st.session_state.get('username')

    if send_dict['submit_button']:
        if not validate(form_properties, "user.buy_item.form", send_dict):
            st.error(get_properties(message, "error.user.buy_item.required"))
        else:
            send_dict['slip_type'] = "buy"
            send_dict['comu_id'] = comu_id
            send_dict['username'] = username
            send_dict['item_id'] = item.get('_id') 

            response = make_api_request(f"slip", data=send_dict, method="POST")
            if response:
                if response['status'] != "success":
                    st.session_state['current_page'] = 'buy_item'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = response['message']
                    st.session_state['prior_status'] = "error"
                    st.rerun()
                else:
                    st.session_state['current_page'] = 'buy_item'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success.user.buy_item.create_slip")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
            else:
                st.session_state['current_page'] = 'buy_item'
                st.session_state['selected_item'] = None
                st.session_state['prior_message'] = get_properties(message, "error.user.buy_item.create_slip")
                st.session_state['prior_status'] = "error"
                st.rerun()




def buy_item():
    st.title(get_properties(message, 'user.buy_item.title'))

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
            with st.expander(label=f"{item['item_name']} / {item['item_price']}", expanded=False):
                if item["item_photo"]:
                    st.image(item["item_photo"])

                st.write(item.get('item_description'))

                buy_button = st.button(label=get_properties(message, 'user.buy_item.button.buy'), key=i, use_container_width=True)
                if buy_button:
                    buy_item_popup(item)



@st.dialog(get_properties(message, 'user.give_reward.title'))
def give_reward_popup(_id : str):
    send_dict = dict()

    send_dict = rendering_form(message, form_properties, "user.give_reward.form", send_dict)
    comu_id = st.session_state.get('comu_id')
    username = st.session_state.get('username')

    if send_dict['submit_button']:
        if not validate(form_properties, "user.give_reward.form", send_dict):
            st.error(get_properties(message, "error.user.give_reward.required"))

        else:
            send_dict['reward_id'] = _id
            send_dict['slip_type'] = "reward"
            send_dict['comu_id'] = comu_id
            send_dict['username'] = username

            response = make_api_request(f"slip", data=send_dict, method="POST")
            if response:
                st.session_state['current_page'] = 'give_reward'
                st.session_state['selected_item'] = None
                st.session_state['prior_message'] = get_properties(message, "success.user.give_reward_popup.create_slip")
                st.session_state['prior_status'] = "success"
                st.rerun()
            else:
                st.session_state['current_page'] = 'give_reward'
                st.session_state['selected_item'] = None
                st.session_state['prior_message'] = get_properties(message, "error.user.give_reward_popup.create_slip")
                st.session_state['prior_status'] = "error"
                st.rerun()


    return send_dict

def give_reward():
    st.session_state['current_page'] = 'give_reward'
    st.title(get_properties(message, 'user.give_reward.title'))

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 아이템 목록 보기
    comu_id = st.session_state.get('comu_id')
    reward_list = make_api_request("reward", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청

    if reward_list is not None and 'reward' in reward_list.keys():
        reward_list = reward_list['reward']
        for idx, reward in enumerate(reward_list):
            with st.container(border=True):
                st.write(f"{reward.get('reward_name')} / {reward.get('reward_money')}")
                st.write(reward.get('reward_description'))

                submit_button = st.button(get_properties(message, 'user.give_reward.button.submit'), key = idx, use_container_width=True)

                if submit_button:
                    give_reward_popup(reward.get('_id'))

            






# admin Reward
def read_delete_reward():
    st.session_state['current_page'] = 'read_delete_reward'
    st.title(get_properties(message, 'admin.read_delete_reward.title'))
    
    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 아이템 목록 보기
    comu_id = st.session_state.get('comu_id')
    reward_list = make_api_request("reward", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청

    col1, col2 = st.columns([1,1])
    with col1:
        submit_button = st.button("CREATE/UPDATE", key="create_update_button", use_container_width=True)
    with col2:
        delete_button = st.button("DELETE", key="delete_button",use_container_width=True)

    if reward_list is not None and 'reward' in reward_list.keys():
        reward_df = pd.DataFrame(reward_list['reward'])

        reward_df.insert(0, 'selected', False)

        edited_df = rendering_data_editor(message, table_properties, "admin.read_delete_reward.table", reward_df)

        selected_reward = edited_df[edited_df['selected']]  # 선택된 행만 필터링
        selected_reward = selected_reward.to_dict(orient='records')

    if submit_button:
        if len(selected_reward) == 0:
            st.session_state['current_page'] = 'create_update_reward'
            st.session_state['selected_reward'] = None
            st.rerun()
        elif len(selected_reward) == 1:
            st.session_state['current_page'] = 'create_update_reward'
            st.session_state['selected_reward'] = selected_reward[0]
            st.rerun()
        else:
            st.error(get_properties(message, "error.admin.read_delete_reward.create_update_selected"))


    if delete_button:
        delete_flag = True
        if len(selected_reward) == 0:
            show_message(get_properties(message, "error.admin.read_delete_reward.delete_selected"), "error")
        else:
            for reward in selected_reward:
                _id = reward.get('_id', None)
                if _id:
                    response = make_api_request(f"reward/{_id}", data=reward, method='DELETE')
                    if response == None:
                        delete_flag = False
                        break
                else:
                    delete_flag = False
            
            if delete_flag:
                st.session_state['prior_message'] = get_properties(message, "success.admin.read_delete_reward.delete")
                st.session_state['prior_status'] = "success"
                st.rerun()
            else:
                show_message(get_properties(message, "error.admin.read_delete_reward.delete"), "error")


            


def create_update_reward():
    st.session_state['current_page'] = 'create_update_reward'

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
    comu_id = st.session_state.get('comu_id') or None
        
    send_dict['comu_id'] = comu_id
    if reward_selected.get("_id", None):
        send_dict['_id'] = reward_selected.get("_id", "").strip()

    submit_button = send_dict['submit_button']

    if back_button:
        st.session_state['current_page'] = 'read_delete_reward'
        st.session_state['selected_item'] = None
        st.rerun()

    if submit_button:
        if validate(form_properties, "admin.create_update_reward.form", send_dict) == False:
            st.error(get_properties(message, "error.admin.create_update_reward.required"))
        else:
            if send_dict.get('_id', None):
                response = make_api_request(f"reward/{send_dict['_id']}", data=send_dict, method='PUT')
                if response:
                    st.session_state['current_page'] = 'read_delete_reward'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success.admin.create_update_reward.update")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error.admin.create_update_reward.update"), "error")
            else:
                response = make_api_request("reward", data=send_dict, method='POST')
                if response:
                    st.session_state['current_page'] = 'read_delete_reward'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success.admin.create_update_reward.create")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error.admin.create_update_reward.create"), "error")


    

def read_inventory():
    st.session_state['current_page'] = 'read_inventory'
    base_path = "user.read_inventory."
    comu_id = st.session_state.get('comu_id')
    username  = st.session_state.get('username')

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    # 인벤토리 목록 보기
    inventory_list = make_api_request("inventory", data={"comu_id": comu_id, "username" : username}) 

    st.title(f"{username}의 " + get_properties(message, base_path + "title"))
    st.subheader(get_properties(message, base_path + "subheader").format(str(inventory_list.get("money", 0))))

    if inventory_list is not None and 'inventory' in inventory_list.keys():
        cols = st.columns(3)
        inventory = inventory_list['inventory']
        for i in range(len(inventory)):
            item = inventory[i]
            with cols[i % 3]:
                with st.expander(label=f"{item['item_name']}", expanded=False):
                    if item["item_photo"]:
                        st.image(item["item_photo"])

                    st.write(item.get('item_description'))

                    use_button = st.button("사용", key = str(i)+"use", use_container_width=True)
                    transfer_button = st.button("양도", key = str(i)+"transfer", use_container_width=True)

                    if transfer_button:
                        read_inventory_popupread_inventory_popup

@st.dialog(get_properties(message, 'user.read_inventory.title'))
def read_inventory_popup(inventory_id : str):
    send_dict = dict()
    comu_id = st.session_state.get('comu_id')
    username = st.session_state.get('username')

    response = make_api_request("users", data={
        "comu_id" : comu_id
    }, method='GET')

    if not response:
        st.error(get_properties(message, 'error.user.read_inventory.user_list'))


    if response is not None and 'users' in response.keys():
        username_list = [user.get("username") for user in response['users']]

        with st.form(key="form"):
            option = st.selectbox(
                get_properties(message, 'user.read_inventory.form.username_to'),
                username_list
            )

            if st.form_submit_button(use_container_width=True):
                if not option:
                    st.error(get_properties(message, "error.user.read_inventory.required"))

                else:
                    send_dict['comu_id'] = comu_id
                    send_dict['username'] =  username
                    send_dict['slip_type'] =  "transfer"
                    send_dict['username_to'] = option
                    send_dict['inventory_id'] =  inventory_id

                    response = make_api_request(f"slip", data=send_dict, method='POST')
                    if response:
                        st.session_state['current_page'] = 'read_inventory'
                        st.session_state['selected_item'] = None
                        st.session_state['prior_message'] = get_properties(message, "success.user.read_inventory.create_slip")
                        st.session_state['prior_status'] = "success"
                        st.rerun()
                    else:
                        st.session_state['current_page'] = 'read_inventory'
                        st.session_state['selected_item'] = None
                        st.session_state['prior_message'] = get_properties(message, "error.user.read_inventory.create_slip")
                        st.session_state['prior_status'] = "error"
                        st.rerun()


    

                        

def read_slip():
    st.session_state['current_page'] = 'read_slip'
    base_path = "user.read_slip."
    comu_id = st.session_state.get('comu_id')
    username  = st.session_state.get('username')

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    slip_list = make_api_request("slip", data={"comu_id": comu_id, "username" : username}) 

    st.title(f"{username}의 " + get_properties(message, base_path + "title"))

    if slip_list is not None and 'slip' in slip_list.keys():
        slip_list = slip_list['slip']

        for idx, slip in enumerate(slip_list):
            with st.container(border=True):
                add_time = slip['add_time']
                add_time = f"{add_time[:4]}/{add_time[4:6]}/{add_time[6:8]} {add_time[8:10]}:{add_time[10:12]}"
                slip_type = slip['slip_type']
                if slip_type == "reward":
                    slip_type = "적립"
                elif slip_type == "buy":
                    slip_type = "구매"
                st.write(f"[{slip_type}][{add_time}]")
                st.write(slip.get('slip_description'))
                st.write(f"자산 변경 : {slip['before_money']} → {slip['after_money']} ({slip['money_change']})")


def read_user():
    st.session_state['current_page'] = 'read_user'
    base_path = "admin.read_user."
    comu_id = st.session_state.get('comu_id')
    username  = st.session_state.get('username')

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    response = make_api_request("user_battle", data={"comu_id": comu_id, "username" : username}) 


def read_delete_monster():
    st.title(get_properties(message, 'admin.read_delete_monster.title'))

    st.session_state['current_page'] = 'read_delete_monster'
    base_path = "admin.read_delete_monster."
    comu_id = st.session_state.get('comu_id')
    username  = st.session_state.get('username')

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    response = make_api_request("monster", data={"comu_id": comu_id})

    col1, col2 = st.columns([1,1])
    with col1:
        create_button = st.button("CREATE/UPDATE", key="create_update_button", use_container_width=True)
    with col2:
        delete_button = st.button("DELETE", key="delete_button",use_container_width=True)

    if isinstance(response, dict) and "monster" in response.keys():
        monster_df = pd.DataFrame(response['monster'])

        monster_df.insert(0, 'selected', False)

        edited_df = rendering_data_editor(message, table_properties, "admin.read_delete_monster.table", monster_df)

        selected_monster = edited_df[edited_df['selected']]  # 선택된 행만 필터링
        selected_monster = selected_monster.to_dict(orient='records')

    if create_button:
        if len(selected_monster) == 0:
            st.session_state['current_page'] = 'create_update_monster'
            st.session_state['selected_monster'] = None
            st.rerun()
        elif len(selected_monster) == 1:
            st.session_state['current_page'] = 'create_update_monster'
            st.session_state['selected_monster'] = selected_monster[0]
            st.rerun()
        else:
            st.error(get_properties(message, "error.admin.read_delete_monster.selected"))

    if delete_button:
        delete_flag = True
        if len(selected_monster) == 0:
            show_message(get_properties(message, "error."+base_path+"delete_selected"), "error")
        else:
            for item in selected_monster:
                _id = item.get('_id', None)
                if _id:
                    response = make_api_request(f"monster/{_id}", data=item, method='DELETE')
                    if response == None:
                        delete_flag = False
                        break
                else:
                    delete_flag = False
            
            if delete_flag:
                st.session_state['prior_message'] = get_properties(message, "success."+base_path+"delete")
                st.session_state['prior_status'] = "success"
                st.rerun()
            else:
                show_message(get_properties(message, "error."+base_path+"delete"), "error")


def create_update_monster():
    st.title(get_properties(message, 'admin.create_update_monster.title'))

    item_selected = st.session_state.get("selected_monster") or {}


    st.session_state['current_page'] = 'create_update_monster'
    base_path = "admin.create_update_monster."
    comu_id = st.session_state.get('comu_id')

    if st.session_state.get('prior_message', None) and st.session_state.get('prior_status', None):
        show_message(st.session_state['prior_message'], st.session_state['prior_status'])
        st.session_state['prior_message'] = None
        st.session_state['prior_status'] = None

    send_dict = rendering_form(message, form_properties, base_path+"form", {}, item_selected)
    send_dict['comu_id'] = comu_id

    if item_selected.get("_id", None):
        send_dict['_id'] = item_selected.get("_id", None)

    if send_dict['submit_button']:
        if not validate(form_properties, base_path+"form", send_dict):
            st.error(get_properties(message, "error." + base_path + "required"))
        else:
            if send_dict.get('_id', None):
                response = make_api_request(f"monster/{send_dict['_id']}", data=send_dict, method='PUT')
                if response:
                    st.session_state['current_page'] = 'read_delete_monster'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success." + base_path + "update")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error." + base_path + "update"), "error")
            else:
                response = make_api_request("monster", data=send_dict, method='POST')
                if response:
                    st.session_state['current_page'] = 'read_delete_monster'
                    st.session_state['selected_item'] = None
                    st.session_state['prior_message'] = get_properties(message, "success." + base_path + "create")
                    st.session_state['prior_status'] = "success"
                    st.rerun()
                else:
                    show_message(get_properties(message, "error." + base_path + "create"), "error")


        




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
                                    [
                                        get_properties(message, 'admin.item_crud.title'),
                                        get_properties(message, 'admin.create_update_reward.title'),
                                        get_properties(message, 'admin.read_delete_monster.title'),
                                        get_properties(message, 'common.menu.logout')])
        
        if options == get_properties(message, 'admin.item_crud.title'):
            if st.session_state['current_page'] != 'create_update_item':
                item_crud()  # 로그인 후 아이템 CRUD 페이지 표시
            else:
                create_update_item()
        elif options == get_properties(message, 'admin.create_update_reward.title'):
            if st.session_state['current_page'] != 'create_update_reward':
                read_delete_reward()  # 로그인 후 아이템 CRUD 페이지 표시
            else:
                create_update_reward()

        elif options == get_properties(message, 'admin.read_delete_monster.title'):
            if st.session_state['current_page'] != 'create_update_monster':
                read_delete_monster()
            else:
                create_update_monster()
    
        elif options == get_properties(message, 'common.menu.logout'):
            logout()
    else:
        options = st.sidebar.radio(get_properties(message, 'main.sidebar.radio.title'), 
                                    [get_properties(message, 'user.buy_item.title'),
                                    get_properties(message, 'user.give_reward.title'),
                                    get_properties(message, "user.read_inventory.title"),
                                    get_properties(message, "user.read_slip.title"),
                                    get_properties(message, 'common.menu.logout')
                                    
                                    ])
        
        if options == get_properties(message, 'user.buy_item.title'):
            buy_item()
        elif options == get_properties(message, 'user.give_reward.title'):
            give_reward()
        elif options == get_properties(message, 'common.menu.logout'):
            logout()
        elif options == get_properties(message, "user.read_inventory.title"):
            read_inventory()
        elif options == get_properties(message, "user.read_slip.title"):
            read_slip()
        
if __name__ == "__main__":
    main()
