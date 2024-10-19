import requests
import streamlit as st

class APIClient:
    def __init__(self, api_url: str):
        self.api_url = api_url

    def make_request(self, endpoint: str, data: dict = None, method: str = 'GET'):
        headers = {}
        data = {key: value for key, value in data.items() if key != "submit_button"}
        
        # sign_up 및 sign_in 엔드포인트에 대해서는 토큰을 검증하지 않음
        if not (endpoint.startswith("sign_up") or endpoint.startswith("sign_in")):
            # 세션 상태에서 토큰 가져오기
            if 'access_token' in st.session_state:
                headers['Authorization'] = f"Bearer {st.session_state['access_token']}"

        # API 요청 처리
        url = f"{self.api_url}/{endpoint}"
        response = None

        if method == 'POST':
            response = requests.post(url, json=data, headers=headers)
        elif method == 'GET':
            response = requests.get(url, headers=headers, params=data)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, json=data)
        
        # 토큰 유효시간 만료 처리
        if response.status_code == 401:
            st.error("인증이 만료되었습니다. 다시 로그인해 주세요.")
            st.session_state.clear()  # 모든 세션 상태 제거
            st.session_state['current_page'] = 'login'  # 로그인 페이지로 돌아가기
            return None

        # 요청이 실패했을 때
        if response.status_code != 200:
            st.error(f"오류가 발생했습니다. 상태 코드: {response.status_code}")
            return None

        # 요청이 성공하면 JSON 응답 반환
        return response.json()
