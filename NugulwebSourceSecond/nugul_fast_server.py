import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from mongodb_manager import MongoDBManager  # MongoDBManager 클래스 파일을 불러옵니다.
from bson import ObjectId
from typing import Optional
import json
from datetime import datetime
import pytz



# FastAPI 인스턴스 생성
app = FastAPI()


# MongoDB Manager 인스턴스 생성 (MongoDB URI와 데이터베이스 이름 설정)
MONGO_URI = "mongodb+srv://quietromance1122:1234@nugulbot.xhbdnfk.mongodb.net/?retryWrites=true&w=majority&appName=Nugulbot"
DB_NAME = "NugulWeb"
db_manager = MongoDBManager(uri=MONGO_URI, db_name=DB_NAME)

# 비밀번호 해싱을 위한 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 설정
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def serialized_data(item):
    for idx in item.keys():
        if isinstance(item[idx], ObjectId):
            item[idx] = str(item[idx])
    return item

# JWT 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 회원가입 데이터 모델
class RegisterUser(BaseModel):
    username: str
    password: str
    comu_id: str
    server_id : str
    battle_room_channel_id : str

@app.get("/user/master")
async def get_user_master(comu_id : str):
    session = None
    user_master = await db_manager.find_documents(session, "user_master", {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(user) for user in user_master]
    return {"user_master_list": serialized_dict}
    

# 회원가입 API 엔드포인트
@app.post("/sign_up")
async def sign_up(user: RegisterUser):
    # 비밀번호 해싱
    hashed_password = pwd_context.hash(user.password)
    
    # MongoDB에 저장할 데이터
    user_data = {
        "username": user.username,
        "password": hashed_password,
        "comu_id": user.comu_id,
        "server_id" : user.server_id,
        "battle_room_channel_id" : user.battle_room_channel_id
    }

    # 중복 유저 검사
    session = None
    existing_user = await db_manager.find_one_document(session, "users", {"username": user.username, "comu_id" : user.comu_id})
    if existing_user:
        raise  HTTPException(status_code=409, detail="Username already taken")

    # 유저 저장
    user_id = await db_manager.create_one_document(session, "users", user_data)

    return {"message": "회원가입 성공", "user_id": str(user_id)}

class LoginForm(BaseModel):
    username: str
    password: str

@app.post("/sign_in")
async def sign_in(form_data: LoginForm):
    session = None
    # comu_id와 username으로 유저 검색
    user = await db_manager.find_one_document(session, "users", {"username": form_data.username})

    # 유저가 없거나 비밀번호가 맞지 않으면 에러 반환
    if not user or not pwd_context.verify(form_data.password, user['password']):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer", "comu_id" : user.get("comu_id"), "message": "로그인 성공", "server_id" : user.get("server_id")}


class UserMaster(BaseModel):
    user_name : str
    battle_type : str
    max_hp : int
    attack : int
    defense : int
    heal : int
    comu_id : str
    server_id : str


@app.post("/user/master")
async def create_user(form_data: UserMaster):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['battle_type'] = send_data['battle_type'].lower()

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        user_master_id = await db_manager.create_one_document(session, "user_master", send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Master created successfully", "user_master_id": str(user_master_id), "status" : "success", "message" : "유저 생성에 성공했습니다."}

@app.put("/user/master/{row_id}")
async def update_user(row_id: str, form_data: UserMaster):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['battle_type'] = send_data['battle_type'].lower()

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, "user_master", {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, "user_master", {"_id": ObjectId(row_id)}, send_data)
            
            extra_query = {
                "server_id" : document.get("server_id"),
                "user_id" : document.get("user_id"),
                "user_name" : document.get("user_name")
            }

            calculate_document = await db_manager.find_one_document(session, "user_calculate", extra_query)

            if calculate_document:
                if calculate_document.get("hp") > send_data.get("max_hp"):
                    send_data['hp'] = send_data.get("max_hp")

                result = await db_manager.update_one_document(session, "user_calculate", extra_query, send_data)
        else:
            raise HTTPException(status_code=404, detail="User Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Master update successfully", "status" : "success", "message" : "유저 업데이트에 성공했습니다."}


@app.delete("/user/master/{row_id}")
async def delete_user_master(row_id: str):
    session = await db_manager.client.start_session()

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, "user_master", {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_documents(session, "user_master", {"_id": ObjectId(row_id)}, document)
            
            extra_query = {
                "server_id" : document.get("server_id"),
                "user_id" : document.get("user_id"),
                "user_name" : document.get("user_name")
            }

            result = await db_manager.update_documents(session, "user_calculate", extra_query, {"del_flag" : True})
            result = await db_manager.update_documents(session, "user_active_skill", extra_query, {"del_flag" : True})
            result = await db_manager.update_documents(session, "user_passive_skill", extra_query, {"del_flag" : True})
            result = await db_manager.update_documents(session, "inventory", extra_query, {"del_flag" : True})
        else:
            raise HTTPException(status_code=404, detail="User Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Master delete successfully", "status" : "success", "message" : "유저 삭제에 성공했습니다."}


# Admin : Reward Start
# 보상 데이터 모델
class Reward(BaseModel):
    reward_name : str
    reward_description : str
    reward_money : int
    comu_id : str
    server_id : str

@app.get("/reward")
async def read_reward(comu_id : str):
    session = None
    collection_name = "reward"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {"reward_list": serialized_dict}

# 보상 마스터 데이터 생성
@app.post("/reward")
async def create_reward(form_data: Reward):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    collection_name = "reward"

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Reward created successfully", "reward_id": str(created_id), "status" : "success", "message" : "보상 데이터 생성에 성공했습니다."}

@app.put("/reward/{row_id}")
async def update_reward(row_id: str, form_data: Reward):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    collection_name = "reward"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, send_data)
        else:
            raise HTTPException(status_code=404, detail="Reward Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Reward updated successfully", "status" : "success", "message" : "보상 데이터 업데이트에 성공했습니다."}


@app.delete("/reward/{row_id}")
async def delete_reward(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "reward"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="Reward Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Reward delete successfully", "status" : "success", "message" : "보상 데이터 삭제에 성공했습니다."}


# 판매 아이템 데이터 모델
class Item(BaseModel):
    item_name: str
    item_description: str
    item_price: int
    item_type: str
    item_formula : Optional[str] = None
    comu_id : str
    server_id : str

@app.get("/item")
async def read_item(comu_id : str):
    session = None
    collection_name = "item"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {"item_list": serialized_dict}

# 보상 마스터 데이터 생성
@app.post("/item")
async def create_item(form_data: Item):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['item_type'] = send_data['item_type'].lower()

    collection_name = "item"

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Item created successfully", "reward_id": str(created_id), "status" : "success", "message" : "아이템 데이터 생성에 성공했습니다."}

@app.put("/item/{row_id}")
async def update_item(row_id: str, form_data: Item):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['item_type'] = send_data['item_type'].lower()
    collection_name = "item"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, send_data)
        else:
            raise HTTPException(status_code=404, detail="Item Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Item updated successfully", "status" : "success", "message" : "아이템 데이터 업데이트에 성공했습니다."}


@app.delete("/item/{row_id}")
async def delete_item(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "item"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="Item Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Item delete successfully", "status" : "success", "message" : "아이템 데이터 삭제에 성공했습니다."}


# 유저 액티브 스킬 데이터 모델
class ActiveSkill(BaseModel):
    user_name : Optional[str] = None
    monster_name : Optional[str] = None
    active_skill_name: str
    active_skill_description: str
    active_skill_type: str
    active_skill_formula : Optional[str] = None
    active_skill_scope : str
    active_skill_condition : Optional[list] = None
    active_skill_hate : Optional[int] = None
    active_skill_turn : Optional[int] = None
    active_skill_scope_number : Optional[int] = 0
    
    active_dot_name : Optional[str] = None
    active_dot_formula : Optional[str] = None
    active_dot_turn : Optional[int] = None

    comu_id : str
    server_id : str

@app.get("/user/skill/active")
async def read_user_active_skill(comu_id : str):
    session = None
    collection_name = "user_active_skill"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {f"{collection_name}_list": serialized_dict}

@app.get("/monster/skill/active")
async def read_monster_active_skill(comu_id : str):
    session = None
    collection_name = "monster_active_skill"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {f"{collection_name}_list": serialized_dict}

@app.post("/user/skill/active")
async def create_user_active_skill(form_data: ActiveSkill):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['active_skill_type'] = send_data['active_skill_type'].lower()
    send_data['active_skill_scope'] = send_data['active_skill_scope'].lower()
    if "active_skill_hate" not in send_data.keys():
        send_data['active_skill_hate'] = 0
    if "active_skill_condition" not in send_data.keys():
        send_data['active_skill_condition'] = list()

    comu_id = send_data['comu_id']

    collection_name = "user_active_skill"

    if send_data['active_skill_type'] == "heal" and 'active_dot_formula' in send_data.keys():
        if not send_data.get("active_dot_name", None):
            send_data['active_dot_name'] = "도트힐"
    elif send_data['active_skill_type'] == "attack" and 'active_dot_formula' in send_data.keys():
        if not send_data.get("active_dot_name", None):
            send_data['active_dot_name'] = "도트딜"
    else:
        send_data['active_dot_name'] = ''
        send_data['active_dot_formula'] = ''
        send_data['active_dot_turn'] = 0

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        user_name = send_data['user_name']
        user_document = await db_manager.find_one_document(session, "user_master", {"comu_id": comu_id, "del_flag" : False, "user_name" : user_name})
        user_id = user_document.get("user_id", None)

        if user_id:
            send_data['user_id'] = user_id

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Active Skill created successfully", f"{collection_name}_id": str(created_id), "status" : "success", "message" : "유저 액티브 스킬 생성에 성공했습니다."}

@app.post("/monster/skill/active")
async def create_monster_active_skill(form_data: ActiveSkill):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['active_skill_type'] = send_data['active_skill_type'].lower()
    send_data['active_skill_scope'] = send_data['active_skill_scope'].lower()
    comu_id = send_data['comu_id']

    collection_name = "monster_active_skill"

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster Active Skill created successfully", f"{collection_name}_id": str(created_id), "status" : "success", "message" : "몬스터 액티브 스킬 생성에 성공했습니다."}

@app.put("/user/skill/active/{row_id}")
async def update_user_active_skill(row_id: str, form_data: ActiveSkill):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['active_skill_type'] = send_data['active_skill_type'].lower()
    send_data['active_skill_scope'] = send_data['active_skill_scope'].lower()
    if "active_skill_hate" not in send_data.keys():
        send_data['active_skill_hate'] = 0
    if "active_skill_condition" not in send_data.keys():
        send_data['active_skill_condition'] = list()
    collection_name = "user_active_skill"

    if send_data['active_skill_type'] == "heal" and 'active_dot_formula' in send_data.keys():
        if not send_data.get("active_dot_name", None):
            send_data['active_dot_name'] = "도트힐"
    elif send_data['active_skill_type'] == "attack" and 'active_dot_formula' in send_data.keys():
        if not send_data.get("active_dot_name", None):
            send_data['active_dot_name'] = "도트딜"
    else:
        send_data['active_dot_name'] = ''
        send_data['active_dot_formula'] = ''
        send_data['active_dot_turn'] = 0

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, send_data)
        else:
            raise HTTPException(status_code=404, detail="User Active Skill is not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Active Skill updated successfully", "status" : "success", "message" : "유저 액티브 스킬 생성에 성공했습니다."}

@app.put("/monster/skill/active/{row_id}")
async def update_monster_active_skill(row_id: str, form_data: ActiveSkill):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    send_data['active_skill_type'] = send_data['active_skill_type'].lower()
    send_data['active_skill_scope'] = send_data['active_skill_scope'].lower()
    collection_name = "monster_active_skill"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, send_data)
        else:
            raise HTTPException(status_code=404, detail="Monster Active Skill is not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster Active Skill updated successfully", "status" : "success", "message" : "몬스터 액티브 스킬 생성에 성공했습니다."}


@app.delete("/user/skill/active/{row_id}")
async def delete_user_active_skill(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "user_active_skill"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="User Active Skill is not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "User Active Skill delete successfully", "status" : "success", "message" : "유저 엑티브 스킬 삭제에 성공했습니다."}

@app.delete("/monster/skill/active/{row_id}")
async def delete_monster_active_skill(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "monster_active_skill"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="Monster Active Skill is not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster Active Skill delete successfully", "status" : "success", "message" : "몬스터 엑티브 스킬 삭제에 성공했습니다."}


# 몬스터 데이터 모델
class Monster(BaseModel):
    monster_name: str
    monster_description: str
    max_hp : int
    attack : int
    defense : int
    heal : int
    comu_id : str
    server_id : str

@app.get("/monster")
async def read_monster(comu_id : str):
    session = None
    collection_name = "monster"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {f"{collection_name}_list": serialized_dict}

@app.post("/monster")
async def create_monster(form_data: Monster):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()

    collection_name = "monster"

    try:
        session.start_transaction()
        send_data['del_flag'] = False

        document = await db_manager.find_one_document(session, collection_name, {
            "del_flag" : False,
            "monster_name" : send_data.get("monster_name")
        })

        if document:
            raise  HTTPException(status_code=409, detail="Monster Name already taken") 

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster created successfully", f"{collection_name}_id": str(created_id), "status" : "success", "message" : "몬스터 생성에 성공했습니다."}

@app.put("/monster/{row_id}")
async def update_monster(row_id: str, form_data: Monster):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    collection_name = "monster"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, send_data)
        else:
            raise HTTPException(status_code=404, detail="Monster Master not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster updated successfully", "status" : "success", "message" : "몬스터 데이터 업데이트에 성공했습니다."}


@app.delete("/monster/{row_id}")
async def delete_monster(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "monster"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="Monster Master not found")

        result = await db_manager.update_documents(
            session,
            "monster_active_skill",
            {
                "del_flag" : False,
                "monster_name" : document.get("monster_name")
            },
            {
                "del_flag" : True
            })

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Monster delete successfully", "status" : "success", "message" : "몬스터 데이터 삭제에 성공했습니다."}

# 몬스터 데이터 모델
class Battle(BaseModel):
    battle_name: str
    server_id : str
    monster_list : list
    comu_id : str

@app.get("/battle")
async def read_battle(comu_id : str):
    session = None
    collection_name = "battle"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "del_flag" : False})

    serialized_dict = [serialized_data(data) for data in data_list]
    return {f"{collection_name}_list": serialized_dict}

@app.get("/battle/log")
async def read_battle_log(comu_id : str, battle_id : str, current_turn : int):
    session = None
    collection_name = "battle_log"
    data_list = await db_manager.find_documents(session, collection_name, {"comu_id": comu_id, "battle_id" : ObjectId(battle_id), "current_turn" : current_turn})

    send_data_list = list()
    for data in data_list:
        send_data = {k : v for k, v in data.items()}

        behavior_type = data.get("action_behavior_type")
        behavior_collection_name = behavior_type + "_calculate"
        behavior_name_collumn = behavior_type + "_name"
        behavior_name = data.get("action_behavior_name")

        behavior_data = await db_manager.find_one_document(session, behavior_collection_name, {"comu_id" : comu_id, behavior_name_collumn : behavior_name, "del_flag" : False})
        if not behavior_data:
            raise HTTPException(status_code=404, detail="Behavior Master not found")

        target_type = data.get("action_target_type")
        target_collection_name = target_type + "_calculate"
        target_name_collumn = target_type + "_name"
        target_name = data.get("action_target_name")

        target_data = await db_manager.find_one_document(session, target_collection_name, {"comu_id" : comu_id, target_name_collumn : target_name, "del_flag" : False})
        if not target_data:
            raise HTTPException(status_code=404, detail="Target Master not found")

        behavior_description = behavior_name + f"\n(hp : {behavior_data.get("hp")}/ hate : {behavior_data.get("hate", "0")})"
        send_data['action_behavior'] = behavior_description
        
        target_description = target_name + f"\n(hp : {target_data.get("hp")}/ hate : {target_data.get("hate", "0")})"
        send_data['action_target'] = target_description

        send_data_list.append(send_data)

    serialized_dict = [serialized_data(data) for data in send_data_list]
    return {f"{collection_name}_list": serialized_dict}

@app.post("/battle")
async def create_battle(form_data: Battle):
    session = await db_manager.client.start_session()
    send_data = form_data.dict()
    comu_id = send_data['comu_id']

    collection_name = "battle"

    try:
        session.start_transaction()
        send_data['del_flag'] = False
        send_data['current_turn'] = 1

        battle_validation_data = await db_manager.find_one_document(session, "users", {"comu_id": comu_id, "battle_name" : send_data.get("battle_name")})
        if battle_validation_data:
            raise  HTTPException(status_code=409, detail="Battle Name already taken")

        user_document = await db_manager.find_one_document(session, "users", {"comu_id": comu_id})
        if not user_document:
            raise HTTPException(status_code=404, detail="Comunity Master not found")

        battle_room_channel_id = user_document.get("battle_room_channel_id")
        send_data['channel_id'] = battle_room_channel_id

        created_id = await db_manager.create_one_document(session, collection_name, send_data)

        monster_list = send_data.get("monster_list")

        monster_calculate_id_list = list()
        for monster in monster_list:
            monster_data = await db_manager.find_one_document(session, "monster", {
                "del_flag" : False,
                "monster_name" : monster
            })

            monster_data['hp'] = monster_data['max_hp']
            monster_data.pop('_id')
            monster_data['battle_name'] = send_data['battle_name']

            monster_calculate_id = await db_manager.create_one_document(session, "monster_calculate", monster_data)
            if monster_calculate_id:
                monster_calculate_id_list.append(str(monster_calculate_id))
            else:
                raise HTTPException(status_code=404, detail="Monster not found")

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Battle created successfully", "channel_id" : battle_room_channel_id, f"{collection_name}_id": str(created_id), "status" : "success", "message" : "배틀 생성에 성공했습니다.", "monster_calculate_id" : monster_calculate_id_list}

@app.delete("/battle/{row_id}")
async def delete_battle(row_id: str):
    session = await db_manager.client.start_session()
    collection_name = "battle"

    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, collection_name, {"_id": ObjectId(row_id)})
        if document:
            document['del_flag'] = True
            result = await db_manager.update_one_document(session, collection_name, {"_id": ObjectId(row_id)}, document)
        else:
            raise HTTPException(status_code=404, detail="Monster Master not found")

        monster_list = document.get("monster_list")

        monster_calculate_list = await db_manager.update_documents(session, "monster_calculate", {
            "del_flag" : False,
            "battle_name" : document.get("battle_name")
        }, {"del_flag" : True})

        user_update_result = await db_manager.update_documents(session, "user_calculate", {
            "del_flag" : False
        }, {"hate" : 0})

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Battle delete successfully", "status" : "success", "message" : "배틀 삭제에 성공했습니다."}


# 다음 턴 생성 클래스
class NextTurnProcess(BaseModel):
    battle_id: str
    server_id: str
    monster_log : Optional[list] = None
    npc_log : Optional[list] = None
    battle_status_list : Optional[list] = None
    comu_id : str


@app.get("/calculate")
async def get_calculation(comu_id : str, collection_type : str):
    session = None

    send_list = list()
    if collection_type == "user":
        send_list = await db_manager.find_documents(session, "user_calculate", {"comu_id": comu_id, "del_flag" : False, "hp" : {"$gt" : 0}})
        send_list = [send_data for send_data in send_list if send_data.get("user_id")]
    elif collection_type == "monster":
        send_list = await db_manager.find_documents(session, "monster_calculate", {"comu_id": comu_id, "del_flag" : False, "hp" : {"$gt" : 0}})
    else:
        raise HTTPException(status_code=400, detail="Invalid Collection Type")

    serialized_dict = [serialized_data(data) for data in send_list]
    return {"calculate_list": serialized_dict}

@app.get("/battle/status")
async def get_battle_status(comu_id : str, battle_id : str, status_type : str = None):
    session = None
    send_list = list()

    battle_document = await db_manager.find_one_document(session, "battle", {"comu_id": comu_id, "del_flag" : False, "_id" : ObjectId(battle_id)})
    if not battle_document:
        raise HTTPException(status_code=404, detail="Battle not found")

    query = {
        "comu_id" : comu_id,
        "del_flag" : False,
        "battle_id" : ObjectId(battle_id),
        "status_end_turn" :{
            "$gte" : battle_document.get("current_turn")
        }
    }

    if status_type:
        query['status_type'] = status_type

    send_list = await db_manager.find_documents(session, "battle_status", query)

    serialized_dict = [serialized_data(data) for data in send_list]
    print(send_list)
    return {"battle_status_list": serialized_dict}


@app.post("/next")
async def go_next_turn(form_data: NextTurnProcess):
    session = await db_manager.client.start_session()
    form_data_dict = form_data.dict()

    battle_id = form_data_dict['battle_id']
    server_id = form_data_dict.get("server_id")
    comu_id = form_data_dict['comu_id']
    monster_log = form_data_dict.get("monster_log")
    battle_status_list = form_data_dict.get("battle_status_list")

    try:
        session.start_transaction()

        # 배틀 정보 찾고
        battle_document = await db_manager.find_one_document(session, "battle", {"comu_id": comu_id, "del_flag" : False, "_id" : ObjectId(battle_id)})
        print({"comu_id": comu_id, "del_flag" : False, "_id" : ObjectId(battle_id)})
        if not battle_document:
            raise HTTPException(status_code=404, detail="Battle not found")

        # 로그 db 에 올리고
        if monster_log:
            log_create_result = await db_manager.create_documents(session, "battle_log", monster_log)
            if not log_create_result:
                raise HTTPException(status_code=500, detail="Log Creation Failed")

        # hp 갱신하고
        for log in monster_log:

            # 사용자 정보 찾고
            user_master_document = await db_manager.find_documents(session, "user_calculate", {"comu_id": comu_id, "del_flag" : False})
            user_master_document = [user for user in user_master_document if user.get("user_id")]
            if not user_master_document:
                raise HTTPException(status_code=404, detail="User Master not found")

            # 몬스터 정보 찾고
            monster_master_document = await db_manager.find_documents(session, "monster_calculate", {"comu_id": comu_id, "del_flag" : False})
            monster_master_document = [monster for monster in monster_master_document if monster.get("monster_name") in battle_document.get("monster_list")]
            if not monster_master_document:
                raise HTTPException(status_code=404, detail="Monster Master not found")


            target_user_id = log.get("action_target_user_id", None)
            update_calculate_data = dict()
            create_status_data = dict()
            
            query = dict()

            if target_user_id:
                target_collection = "user_calculate"
                target = [user for user in user_master_document if user.get("user_id") == target_user_id]
                if not target:
                    raise HTTPException(status_code=404, detail=f"User({target_user_id}) not found")
                target = target[0]

                target_name = target.get("user_name")

                query = {
                    "comu_id" : comu_id,
                    "user_name" : target.get("user_name"),
                    "user_id" : target_user_id,
                    "del_flag" : False
                }
            else:
                target_collection = "monster_calculate"
                target = [monster for monster in monster_master_document if monster.get("monster_name") == log.get("action_target")]
                if not target:
                    raise HTTPException(status_code=404, detail=f"Monster ({log.get("action_target")}) not found")

                target = target[0]

                target_name = target.get("monster_name")

                query = {
                    "comu_id" : comu_id,
                    "del_flag" : False,
                    "monster_name" : target.get("monster_name")
                }

            
            if log.get("action_type") == "attack":
                org_hp = target.get("hp")
                update_hp = max(0, org_hp - log.get("action_result"))
                update_calculate_data = {
                    "hp" : update_hp
                }

            elif log.get("action_type") == "heal":
                org_hp = target.get("hp")
                update_hp = min(target.get("max_hp"), org_hp + log.get("action_result"))
                update_calculate_data = {
                    "hp" : update_hp
                }

            elif log.get("action_type") == "defense":
                create_status_data = {
                    "server_id" : server_id,
                    "channel_id" : battle_document.get("channel_id"),
                    "comu_id" : comu_id,
                    "battle_name" : battle_document.get("battle_name"),
                    "battle_id" : ObjectId(str(battle_document.get("_id"))),
                    "status_type" : log.get("action_type"),
                    "status_target_collection_name" : target_collection,
                    "status_formula" : log.get("action_result"),
                    "status_target" : target_name,
                    "status_end_turn" : battle_document.get("current_turn") + 2,
                    "del_flag" : False
                }

            if query and update_calculate_data:
                update_result = await db_manager.update_one_document(session, target_collection, query, update_calculate_data)
            
            if create_status_data:
                create_status_result = await db_manager.create_one_document(session, "battle_status", create_status_data)
                if not create_status_result:
                    raise HTTPException(status_code=500, detail="Battle Status Create Failed")

        # 모든 status 를 찾고
        status_query = {
            "comu_id" : comu_id,
            "battle_id" : ObjectId(str(battle_document.get("_id"))),
            "del_flag" : False,
            "status_end_turn" : {
                "$gte"  : battle_document.get("current_turn", 1)
            }
        }

        status_document = await db_manager.find_documents(session, "battle_status", status_query)

        print("debug1")
        print(status_document)
        
        # defense status 바꾸고
        for status in battle_status_list:
            print("debug2")
            print(status)

            status_id = str(status.pop("_id"))
            


            if not any(str(d.get("_id")) == status_id for d in status_document):
                raise HTTPException(status_code=500, detail="Battle Status Not Found")

            status['battle_id'] = ObjectId(str(status['battle_id']))
            update_battle_status_result = await db_manager.update_one_document(session,"battle_status", {"_id" : ObjectId(status_id)}, status)

        # 도트딜 / 도트힐 반영
        status_document = await db_manager.find_documents(session, "battle_status", status_query)

        total_dot_description = "========================\n"

        for status in status_document:
            status_type = status.get('status_type')
            if "dot" not in status_type:
                continue

            print("debug3")
            print("status : ", status)

            # - 도트딜 / 도트힐 로그 생성
            now = datetime.now()
            now = int(now.timestamp() * 1000)

            status_dot_log = {
                "server_id" : status.get("server_id"),
                "channel_id" : status.get("channel_id"),
                "comu_id" : status.get("comu_id"),
                "battle_name" : status.get("battle_name"),
                "battle_id" : ObjectId(str(status.get("battle_id"))),
                "current_turn" :  battle_document.get("current_turn"),
                "action_time" : now,
                "action_behavior_name" : status.get("status_behavior_name"),
                "action_bahavior_user_id" : status.get("status_bahavior_user_id"),
                "action_behavior_type" : "user",
                "action_target_name" : status.get("status_target")
            }

            dot_result_list = status.get("status_formula")
            dot_index = status.get("status_end_turn") - battle_document.get("current_turn")
            dot_result = dot_result_list[dot_index]
            status_dot_log["action_result"] = dot_result

            status_target_collection_name = status.get("status_target_collection_name")
            status_target_name = status.get("status_target")
            
            if "monster" in status_target_collection_name:
                status_target_query = {
                    "battle_name" : status.get("battle_name"),
                    "del_flag" : False,
                    "monster_name" : status_target_name,
                    "hp" :{
                        "$gt" :0
                    }
                }
            else:
                status_target_query = {
                    "del_flag" : False,
                    "user_name" : status_target_name,
                    "comu_id" : comu_id,
                    "hp" :{
                        "$gt" :0
                    }
                }

            print("target query", status_target_query)
            

            dot_target = await db_manager.find_one_document(session, status_target_collection_name, status_target_query)
            print("dot_target", dot_target)
            if not dot_target:
                continue

            if status_type == "dot_heal":
                status_dot_log['action_target_type'] = "party"
                status_dot_log['action_type'] = "heal"
                status_dot_log["action_description"] = f"[{status.get('status_name', '도트힐')}][{status.get('status_behavior_name')} → {status.get('status_target')}] 최종 회복 : {dot_result}"
                total_dot_description += status_dot_log["action_description"]
                total_dot_description += "\n"

                # - 도트딜 / 도트힐 calculation 반영
                final_dot_hp = min(dot_target.get("max_hp"), dot_target.get("hp") + dot_result)
                print("final_dot_hp : ", final_dot_hp)
                dot_result = await db_manager.update_one_document(session, status_target_collection_name, status_target_query, {"hp" : final_dot_hp})

            else:
                status_dot_log['action_target_type'] = "enemy"
                status_dot_log['action_type'] = "attack"
                status_dot_log["action_description"] = f"[{status.get('status_name', '도트딜')}][{status.get('status_behavior_name')} → {status.get('status_target')}] 데미지 : {dot_result}"
                total_dot_description += status_dot_log["action_description"]
                total_dot_description += "\n"

                # - 도트딜 / 도트힐 calculation 반영
                final_dot_hp = max(0, dot_target.get("hp") - dot_result)
                print("final_dot_hp : ", final_dot_hp)
                dot_result = await db_manager.update_one_document(session, status_target_collection_name, status_target_query, {"hp" : final_dot_hp})

            dot_result = await db_manager.create_one_document(session, "battle_log", status_dot_log)

        # 턴 바꾸고
        battle_turn_update_result = await db_manager.update_inc_documents(session, "battle", {"comu_id": comu_id, "del_flag" : False, "_id" : ObjectId(battle_id)}, {"current_turn" : 1})
        if not battle_turn_update_result:
            raise HTTPException(status_code=500, detail="Battle Turn Increase Failed")

        # 바뀐 턴을 반영하여 status_document 재정리
        status_document = [status for status in status_document if status.get("status_end_turn") > battle_document.get("current_turn", 1)]

        # 유저 정보 전송 메세지 생성 
        user_master_document = await db_manager.find_documents(session, "user_calculate", {"comu_id": comu_id, "del_flag" : False})
        user_master_document = [user for user in user_master_document if user.get("user_id")]
        if not user_master_document:
            raise HTTPException(status_code=404, detail="User Master not found")

        user_description = "========================\n"
        sorted_hate = sorted(user_master_document, key=lambda x: x.get("hate", 0), reverse=True)
        chunk = "[헤이트 순서]\n"
        for idx, user in enumerate(sorted_hate):
            chunk += f"{user.get("user_name")} ({user.get("hate", 0)})"
            if idx != len(sorted_hate) -1:
                chunk += " → "

        user_description += chunk
        user_description += "\n"

        sorted_hp = sorted(user_master_document, key=lambda x: x["hp"], reverse=False)
        chunk = "[HP 순서]\n"
        for idx, user in enumerate(sorted_hp):
            chunk += f"{user.get("user_name")} ({user.get("hp")} / {user.get("max_hp")})"
            if idx != len(sorted_hate) -1:
                chunk += " → "
        
        user_description += chunk
        user_description += "\n"

        # status description 추가
        status_description = None
        if status_document:
            status_description = "========================\n"
            for status in status_document:
                status_type = status.get("status_type")
                status_target = status.get("status_target")
                status_end_turn = status.get("status_end_turn")
                remain_turn = status_end_turn - battle_document.get("current_turn", 1)

                if status_type == "defense":
                    status_description += f"[{status_type}][{status_target}] {status.get("status_formula")} 방어벽 ({remain_turn} 턴)\n"



        monster_master_document = await db_manager.find_documents(session, "monster_calculate", {"comu_id": comu_id, "del_flag" : False})
        monster_master_document = [monster for monster in monster_master_document if monster.get("monster_name") in battle_document.get("monster_list")]
        if not monster_master_document:
            raise HTTPException(status_code=404, detail="Monster Master not found")

        monster_master_document = sorted(monster_master_document, key=lambda x: x["hp"], reverse=True)
        monster_description = "========================\n"
        for monster in monster_master_document:
            chunk = f"{monster.get("monster_name")}의 체력 : {monster.get("hp")} / {monster.get("max_hp")}\n"
            monster_description += chunk

        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Go next turn successfully", "status" : "success", "monster_description" :monster_description, "user_description" : user_description, "status_description" : status_description, "dot_description" : total_dot_description}



