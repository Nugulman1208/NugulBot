from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
print(MONGO_URI)
print(DB_NAME)


# MongoDB 연결
client = MongoClient(MONGO_URI)

# 대상 데이터베이스 선택
db = client[DB_NAME]

# 대체할 값 정의
original_value = "hwii1224_97766"
new_value = "mjoo_310"

# 데이터베이스의 모든 컬렉션 가져오기
collections = db.list_collection_names()

for collection_name in collections:
    collection = db[collection_name]
    
    # 컬렉션의 모든 문서 검색 및 업데이트
    for document in collection.find():
        updated = False  # 업데이트 여부 확인
        updated_document = dict()
        
        # 문서의 모든 키를 순회
        for key, value in document.items():
            if value == original_value:
                updated_document[key] = new_value
                updated = True
        
        # 업데이트된 경우 문서 갱신
        if updated:
            collection.update_one({"_id": document["_id"]}, {"$set": updated_document})
            print(f"Updated document in {collection_name}: {document['_id']}")

print("Value replacement complete.")