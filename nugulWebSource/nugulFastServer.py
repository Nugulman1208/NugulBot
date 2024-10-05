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
    is_admin: bool
    comu_id: str  # 변경된 필드명
    photo : Optional[str] = None

@app.get("/users")
async def get_users(comu_id : str):
    session = None
    users = await db_manager.find_documents(session, "users", {"comu_id": comu_id, "is_admin" : False})

    for user in users:
        user.pop("password")

    serialized_dict = [serialize_item(user) for user in users]
    return {"users": serialized_dict}
    

# 회원가입 API 엔드포인트
@app.post("/register")
async def register_user(user: RegisterUser):
    # 비밀번호 해싱
    hashed_password = pwd_context.hash(user.password)
    
    # MongoDB에 저장할 데이터
    user_data = {
        "username": user.username,
        "password": hashed_password,
        "is_admin": user.is_admin,
        "comu_id": user.comu_id,
        "photo": user.photo
    }

    # 중복 유저 검사
    session = None
    existing_user = await db_manager.find_one_document(session, "users", {"username": user.username, "comu_id" : user.comu_id})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # 유저 저장
    user_id = await db_manager.create_one_document(session, "users", user_data)

    calculated_id = ""
    if not user.is_admin:
        calculated_id = await db_manager.create_one_document(session, "user_calculate", {
            "username": user.username,
            "photo": user.photo,
            "comu_id": user.comu_id,
            "max_hp" : 100,
            "pure_atk" : 5,
            "pure_def" : 5,
            "pure_heal" : 5,
            "pure_acc" : 100
            })

    return {"message": "User registered successfully", "user_id": str(user_id), "calculated_id" : str(calculated_id)}

class LoginForm(BaseModel):
    username: str
    password: str
    comu_id: str

@app.post("/login")
async def login_user(form_data: LoginForm):
    session = None
    # comu_id와 username으로 유저 검색
    user = await db_manager.find_one_document(session, "users", {"username": form_data.username, "comu_id": form_data.comu_id})

    # 유저가 없거나 비밀번호가 맞지 않으면 에러 반환
    if not user or not pwd_context.verify(form_data.password, user['password']):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer", "is_admin" : user.get("is_admin")}

# 판매 아이템 데이터 모델
class Item(BaseModel):
    item_name: str
    item_description: str
    item_price: int
    item_type: str
    item_formula : Optional[str] = None
    item_photo : Optional[str] = None
    comu_id : str

# 1. 판매 아이템 생성
@app.post("/items")
async def create_item(item: Item):
    item_data = item.dict()

    session = None
    item_id = await db_manager.create_one_document(session, "items", item_data)
    return {"message": "Item created successfully", "item_id": str(item_id)}

def serialize_item(item):
    for idx in item.keys():
        if isinstance(item[idx], ObjectId):
            item[idx] = str(item[idx])
    return item

# 2. 판매 아이템 목록 조회
@app.get("/items")
async def get_items(comu_id : str = None):
    session = None
    items = await db_manager.find_documents(session, "items", {"comu_id" : comu_id})
    serialized_items = [serialize_item(item) for item in items]
    return {"items": serialized_items}

# 3. 특정 판매 아이템 수정
@app.put("/items/{item_id}")
async def update_item(item_id: str, item: Item):
    session = None
    item_data = item.dict()
    document = await db_manager.find_one_document(session, "items", {"_id": ObjectId(item_id)})
    if document:
        result = await db_manager.update_one_document(session, "items", {"_id": ObjectId(item_id)}, item_data)
    else:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item updated successfully"}

# 4. 판매 아이템 삭제
@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    session = None
    result = await db_manager.remove_one_document(session, "items", {"_id": ObjectId(item_id)})
    if result == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item deleted successfully"}

# Admin : Reward Start
# 보상 데이터 모델
class Reward(BaseModel):
    reward_name : str
    reward_description : str
    reward_money : int
    comu_id : str

# 1. 보상 생성
@app.post("/reward")
async def create_reward(reward: Reward):
    reward_data = reward.dict()

    session = None
    reward_id = await db_manager.create_one_document(session, "reward", reward_data)
    return {"message": "Item created successfully", "reward_id": str(reward_id)}

# 2. 보상 목록 조회
@app.get("/reward")
async def get_reward(comu_id : str = None):
    session = None
    rewards = await db_manager.find_documents(session, "reward", {"comu_id" : comu_id})
    serialized_reward = [serialize_item(reward) for reward in rewards]
    return {"reward": serialized_reward}

# 3. 특정 판매 아이템 수정
@app.put("/reward/{reward_id}")
async def update_reward(reward_id: str, reward: Reward):
    session = None
    reward_data = reward.dict()
    document = await db_manager.find_one_document(session, "reward", {"_id": ObjectId(reward_id)})
    if document:
        result = await db_manager.update_one_document(session, "reward", {"_id": ObjectId(reward_id)}, reward_data)
    else:
        raise HTTPException(status_code=404, detail="Reward not found")
    return {"message": "Item updated successfully"}

# 전표 생성 (적립)
class Slip(BaseModel):
    comu_id : str
    username : str
    slip_type : str
    slip_description : Optional[str] = None
    reward_id :  Optional[str] = None
    reward_count : Optional[int] = None
    item_id :  Optional[str] = None
    item_count : Optional[int] = None
    money_change : Optional[int] = None
    username_to : Optional[str] = None
    inventory_id : Optional[str] = None

@app.post("/slip")
async def create_slip(slip: Slip):
    session = await db_manager.client.start_session()
    slip_data = slip.dict()

    comu_id = slip_data["comu_id"]
    username = slip_data["username"]
    slip_type = slip_data["slip_type"]
    kst = pytz.timezone('Asia/Seoul')
    current_time = datetime.now(kst).strftime("%Y%m%d%H%M%S")

    try:
        # 트랜잭션 시작
        session.start_transaction()

        # 사용자 조회
        user = await db_manager.find_one_document(session, "users", {"username": username, "comu_id": comu_id})
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        result = None

        if slip_type == "reward":
            reward_id = slip_data.get("reward_id")
            if not reward_id:
                raise HTTPException(status_code=400, detail="Reward ID is required for reward slip")

            # 보상 정보 조회
            reward = await db_manager.find_one_document(session, "reward", {"_id": ObjectId(reward_id)})
            if reward is None:
                raise HTTPException(status_code=404, detail="Reward not found")

            reward_money = reward.get('reward_money', 0)
            reward_count = slip_data.get("reward_count", 1)
            reward_name = reward.get('reward_name', '')
            slip_description = f"적립({reward_name}) x {reward_count}"
            slip_data['slip_description'] = slip_description
            slip_data['money_change'] = reward_money * reward_count
            before_money = user.get("money", 0)
            after_money = before_money + slip_data['money_change']
            slip_data['before_money'] = before_money
            slip_data['after_money'] = after_money
            slip_data['reward_money'] = reward_money
            slip_data['add_time'] = current_time

            # 유저 돈 업데이트
            count, _id = await db_manager.update_inc_documents(
                session, 
                "users", 
                {"username": username, "comu_id": comu_id}, 
                {"money": slip_data.get('money_change', 0)}
            )

            if count == 0:
                await session.abort_transaction()
                raise HTTPException(status_code=404, detail="User not found or update failed")

            # slip 기록 생성
            result = await db_manager.create_one_document(session, "slip", slip_data)
        
        elif slip_type == "buy":
            item_id = slip_data.get("item_id")
            if not item_id:
                raise HTTPException(status_code=400, detail="Item ID is required for buy slip")

            item = await db_manager.find_one_document(session, "items", {"_id": ObjectId(item_id)})
            if item is None:
                raise HTTPException(status_code=404, detail="Item not found")

            before_money = user.get("money", 0)
            slip_data['money_change'] = item.get('item_price', 0) * slip_data.get('item_count', 0) * -1
            after_money = before_money + slip_data['money_change']

            if after_money < 0:
                await session.abort_transaction()
                return {"message": get_properties(message, "error.user.buy_item.no_money"), "status" : "no_money"}

            slip_description = f"구매({item.get('item_name')}) x {slip_data.get('item_count')}"
            slip_data['slip_description'] = slip_description
            slip_data['before_money'] = before_money
            slip_data['after_money'] = after_money
            slip_data['add_time'] = current_time

            # 유저 돈 업데이트
            count, _id = await db_manager.update_inc_documents(
                session, 
                "users", 
                {"username": username, "comu_id": comu_id}, 
                {"money": slip_data.get('money_change', 0)}
            )

            

            if count == 0:
                await session.abort_transaction()
                raise HTTPException(status_code=404, detail="User not found or update failed")

            # 인벤토리에 넣기
            for _ in range(slip_data.get('item_count', 0)):
                inventory_item = item.copy()
                inventory_item['item_id'] = inventory_item.get("_id")
                inventory_item.pop("_id", None)
                inventory_item['username'] = username
                inventory_item['comu_id'] = comu_id

                inv_id = await db_manager.create_one_document(session, "inventory", inventory_item)

                if not inv_id:
                    await session.abort_transaction()
                    raise HTTPException(status_code=404, detail="Inventory create failed")

            # slip 기록 생성
            result = await db_manager.create_one_document(session, "slip", slip_data)

        elif slip_type == "transfer":
            inventory = await db_manager.find_one_document(session, "inventory", {"_id" : ObjectId(slip_data.get("inventory_id", ""))})

            if not inventory:
                raise HTTPException(status_code=400, detail="Inventory Not Found")

            item_id = inventory.get("item_id")
            
            if not item_id:
                raise HTTPException(status_code=400, detail="Item ID is required for buy slip")

            item = await db_manager.find_one_document(session, "items", {"_id": ObjectId(item_id)})
            if item is None:
                raise HTTPException(status_code=404, detail="Item not found")

            user_from = user
            user_to = await db_manager.find_one_document(session, "users", {"username": slip_data.get("username_to", ""), "comu_id": comu_id})
            if user_to is None:
                raise HTTPException(status_code=404, detail="User not found")

            slip_data["username_from"] = user_from.get("username")
            slip_data["slip_description"] = f"아이템({item.get("item_name")}) 양도 ({user_from.get("username")} → {user_to.get("username")})"
            slip_data['before_money'] = user_from.get("money")
            slip_data['after_money'] = user_from.get("money")
            slip_data['money_change'] = 0
            slip_data['add_time'] = current_time

            result = await db_manager.update_one_document(session, "inventory", {"_id": ObjectId(slip_data.get("inventory_id", ""))}, {
                "username" : user_to.get("username")
            })

            if not result:
                raise HTTPException(status_code=404, detail="Cannot update inventory")

            result = await db_manager.create_one_document(session, "slip", slip_data)

            another_slip_data = slip_data.copy()
            another_slip_data['username'] = user_to.get("username")
            another_slip_data.pop("_id", None)

            result = await db_manager.create_one_document(session, "slip", another_slip_data)
            
        # 트랜잭션 커밋
        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료

    return {"message": "Slip created successfully", "slip_id": str(result) if result else None, "status" : "success"}



# 2. 인벤토리 목록 조회
@app.get("/inventory")
async def get_inventory(comu_id : str = None, username : str = None):
    session = None
    
    user = await db_manager.find_one_document(session, "users", {"username": username, "comu_id": comu_id})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    inventory = await db_manager.find_documents(session, "inventory", {"comu_id" : comu_id, "username" : username})

    serialized_inventory = [serialize_item(inv) for inv in inventory]
    return {"inventory": serialized_inventory, "money" : user.get("money", 0)}

# 3. 전표 목록 조회
@app.get("/slip")
async def get_slip(comu_id : str = None, username : str = None):
    session = None
    
    user = await db_manager.find_one_document(session, "users", {"username": username, "comu_id": comu_id})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    slip = await db_manager.find_documents(session, "slip", {"comu_id" : comu_id, "username" : username})

    serialized_slip = [serialize_item(s) for s in slip]
    return {"slip": serialized_slip}


# 4. 판매 아이템 삭제
@app.delete("/reward/{reward_id}")
async def delete_reward(reward_id: str):
    session = None
    result = await db_manager.remove_one_document(session, "reward", {"_id": ObjectId(reward_id)})
    if result == 0:
        raise HTTPException(status_code=404, detail="Reward not found")
    return {"message": "Reward deleted successfully"}


# 배틀 생성
class Battle(BaseModel):
    comu_id : str
    battle_name : str
    monster_list : Optional[list] = None

class Monster(BaseModel):
    comu_id : str
    monster_name : str
    max_hp : int
    pure_atk : int
    pure_def : int
    pure_heal : int
    pure_acc : int

@app.get("/battle")
async def get_battle(comu_id : str = None):
    session = None

    battle = await db_manager.find_documents(session, "battle", {"comu_id" : comu_id})
    serialized_battle = [serialize_item(s) for s in battle]

    return {"battle" : serialized_battle}

@app.get("/monster")
async def get_monster(comu_id : str = None):
    session = None

    monster = await db_manager.find_documents(session, "monster", {"comu_id" : comu_id})
    serialized_monster = [serialize_item(m) for m in monster]

    return {"monster" : serialized_monster}

@app.post("/monster")
async def create_reward(monster: Monster):
    monster_data = monster.dict()

    session = await db_manager.client.start_session()

    try:
        session.start_transaction()

        monster_id = await db_manager.create_one_document(session, "monster", monster_data)
        if not monster_id:
            await session.abort_transaction()
            raise HTTPException(status_code=500, detail=f"Transaction failed.")
        else:
            await session.commit_transaction()
    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    finally:
        await session.end_session()  # 세션 종료
    return {"message": "Monster created successfully", "monster_id": str(monster_id)}

# 3. 특정 판매 아이템 수정
@app.put("/monster/{monster_id}")
async def update_monster(monster_id: str, monster: Monster):
    session = await db_manager.client.start_session()
    monster_data = monster.dict()
    try:
        session.start_transaction()

        document = await db_manager.find_one_document(session, "monster", {"_id": ObjectId(monster_id)})
        if document:
            result = await db_manager.update_one_document(session, "monster", {"_id": ObjectId(monster_id)}, monster_data)

            await session.commit_transaction()
        
        else:
            raise HTTPException(status_code=404, detail="Monster not found")
    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        await session.end_session()  # 세션 종료
    return {"message": "Monster updated successfully"}

# 4. 판매 아이템 삭제
@app.delete("/monster/{monster_id}")
async def delete_reward(monster_id: str):
    session = await db_manager.client.start_session()

    try:
        session.start_transaction()
        
        result = await db_manager.remove_one_document(session, "monster", {"_id": ObjectId(monster_id)})
        if result == 0:
            raise HTTPException(status_code=404, detail="Monster not found")

        await session.commit_transaction()

    except Exception as e:
        await session.abort_transaction()  # 트랜잭션 롤백
        print(e)
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        await session.end_session()  # 세션 종료
    return {"message": "Monster deleted successfully"}

# 로그아웃은 클라이언트 측에서 처리됩니다.
