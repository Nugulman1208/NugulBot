import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from mongodb_manager import MongoDBManager  # MongoDBManager 클래스 파일을 불러옵니다.
from bson import ObjectId

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
    photo: str

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
    return {"message": "User registered successfully", "user_id": str(user_id)}

class LoginForm(BaseModel):
    username: str
    password: str
    comu_id: str

@app.post("/login")
async def login_user(form_data: LoginForm):
    session = None
    # comu_id와 username으로 유저 검색
    user = await db_manager.find_one_document(session, "users", {"username": form_data.username, "comu_id": form_data.comu_id})

    print(user)
    # 유저가 없거나 비밀번호가 맞지 않으면 에러 반환
    if not user or not pwd_context.verify(form_data.password, user['password']):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# 판매 아이템 데이터 모델
class Item(BaseModel):
    name: str
    description: str
    price: float
    quantity: int

# 1. 판매 아이템 생성
@app.post("/items")
async def create_item(item: Item):
    item_data = item.dict()
    session = None
    item_id = await db_manager.create_one_document(session, "items", item_data)
    return {"message": "Item created successfully", "item_id": str(item_id)}

# 2. 판매 아이템 목록 조회
@app.get("/items")
async def get_items():
    session = None
    items = await db_manager.find_documents(session, "items", {})
    return {"items": items}

# 3. 특정 판매 아이템 수정
@app.put("/items/{item_id}")
async def update_item(item_id: str, item: Item):
    session = None
    item_data = item.dict()
    result = await db_manager.update_document(session, "items", {"_id": ObjectId(item_id)}, item_data)
    if result[0] == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item updated successfully"}

# 4. 판매 아이템 삭제
@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    session = None
    result = await db_manager.remove_document(session, "items", {"_id": ObjectId(item_id)})
    if result == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item deleted successfully"}

# 로그아웃은 클라이언트 측에서 처리됩니다.
