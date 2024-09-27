# google_sheet_manager.py
import aiohttp
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os

class GoogleSheetManager:
    SPREAD_TEMPLATE_ID = "1Ls9MWREceMatPOGWYYKboahvQnS9bbg3rxY53vmlu5g"
    SHEET_URL_PREFIX = "https://docs.google.com/spreadsheets/d/"
    GOOGLE_CREDENTIAL_FILE = "nugulbotproject-b41195cbf552.json"
    SHEET_NAME_LIST = ['USER_INFORMATION', 'ITEM_INFORMATION', 'REWARD_INFORMATION', 'MONSTER_INFORMATION', 'USER_SKILL_INFORMATION', 'BATTLE_TYPE_INFORMATION', 'MONSTER_SKILL_INFORMATION']

    async def get_data_from_google_sheet(self, sheet_id, sheet_name):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, self.GOOGLE_CREDENTIAL_FILE)
            creds = Credentials.from_service_account_file(path, scopes=scope)
            creds.refresh(Request())
            googleClient = gspread.authorize(creds)

            sheet = googleClient.open_by_key(sheet_id).worksheet(sheet_name)
            data = sheet.get_all_values()
            rowList = data[2]

            dataList = []
            for row in data[3:]:
                row_dict = {rowList[i]: row[i] for i in range(len(rowList))}
                dataList.append(row_dict)

            return rowList, dataList, True
        except Exception as e:
            print(e)
            return None, None, False

    async def copy_file_and_set_permission(self, comu_name, email):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, self.GOOGLE_CREDENTIAL_FILE)
            creds = Credentials.from_service_account_file(path, scopes=scope)
            creds.refresh(Request())
            drive_service = build('drive', 'v3', credentials=creds)

            async with aiohttp.ClientSession() as session:
                copy_url = f'https://www.googleapis.com/drive/v3/files/{self.SPREAD_TEMPLATE_ID}/copy'
                headers = {
                    'Authorization': f'Bearer {creds.token}',
                    'Content-Type': 'application/json'
                }
                copy_payload = {'name': comu_name}
                async with session.post(copy_url, headers=headers, json=copy_payload) as copy_resp:
                    copy_data = await copy_resp.json()
                    copied_sheet_id = copy_data['id']

                permission_url = f'https://www.googleapis.com/drive/v3/files/{copied_sheet_id}/permissions'
                permission_payload = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': email
                }
                async with session.post(permission_url, headers=headers, json=permission_payload) as perm_resp:
                    await perm_resp.json()

            return copied_sheet_id, True
        except Exception as e:
            print(e)
            return None, False

            
