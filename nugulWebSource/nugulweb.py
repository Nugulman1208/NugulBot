import streamlit as st
import requests

API_URL = "http://localhost:8000"

# 회원가입 페이지
def register():
    st.title("Register")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    is_admin = st.checkbox("Admin")
    comu_id = st.text_input("Community ID")
    photo = st.file_uploader("Upload a Photo", type=["png", "jpg"])

    if st.button("Register"):
        response = requests.post(f"{API_URL}/register", json={
            "username": username,
            "password": password,
            "is_admin": is_admin,
            "comu_id": comu_id,
            "photo": photo.read().decode("latin-1") if photo else ""
        })
        st.write(response.json())

# 로그인 페이지
def login():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    comu_id = st.text_input("Community ID")
    
    if st.button("Login"):
        response = requests.post(f"{API_URL}/login", json={
            "username": username,
            "password": password,
            "comu_id": comu_id
        })
        if response.status_code == 200:
            st.success("Login successful")
            token_data = response.json()
            st.session_state['access_token'] = token_data['access_token']
            st.session_state['is_admin'] = True
            st.session_state['comu_id'] = comu_id
            st.session_state['login_status'] = True  # 로그인 상태 저장
            st.session_state['current_page'] = 'item_crud'  # 현재 페이지 설정
            st.rerun()  # 페이지 리프레시
        else:
            st.error("Invalid username or password")

# API 요청 처리 함수
def make_api_request(endpoint, data=None, method='GET'):
    headers = {}
    if 'access_token' in st.session_state:
        headers['Authorization'] = f"Bearer {st.session_state['access_token']}"
    
    if method == 'POST':
        response = requests.post(f"{API_URL}/{endpoint}", json=data, headers=headers)
    else:
        response = requests.get(f"{API_URL}/{endpoint}", headers=headers)
    
    # 토큰 유효시간 만료 처리
    if response.status_code == 401:
        st.error("Session expired. Please log in again.")
        st.session_state.clear()  # 모든 세션 상태 제거
        st.session_state['current_page'] = 'login'  # 로그인 페이지로 돌아가기
        return None  # None을 반환하여 로그인 페이지로 돌아가게 합니다.
    
    return response.json()

# 아이템 CRUD 페이지 (관리자 전용)
def item_crud():
    st.title("Item CRUD (Admin Only)")

    # 아이템 목록 보기
    st.subheader("Item List")
    comu_id = st.session_state.get('comu_id')
    items = make_api_request("items", data={"comu_id": comu_id})  # 특정 comu_id에 따른 아이템 요청
    if items is not None:
        st.write(items)

    # 새 아이템 추가
    st.subheader("Add New Item")
    item_name = st.text_input("Item Name")
    item_price = st.number_input("Item Price", min_value=0)
    if st.button("Add Item"):
        response = make_api_request("items", data={
            "name": item_name,
            "price": item_price,
            "comu_id": comu_id
        }, method='POST')
        if response:
            st.success("Item added successfully")
        else:
            st.error("Failed to add item")

# 메인 화면
def main():
    st.sidebar.title("Navigation")

    if 'login_status' not in st.session_state or not st.session_state['login_status']:
        options = st.sidebar.radio("Go to", ["Login", "Register"])
        
        if options == "Login":
            login()
        elif options == "Register":
            register()
    else:
        options = st.sidebar.radio("Go to", ["Item"])
        
        if options == "Item":
            item_crud()  # 로그인 후 아이템 CRUD 페이지 표시

if __name__ == "__main__":
    main()
