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
        "server_id" : user.server_id
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