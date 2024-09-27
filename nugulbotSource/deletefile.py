from pymongo import MongoClient

# MongoDB 클라이언트 설정

MONGO_URI = "mongodb+srv://quietromance1122:1234@nugulbot.xhbdnfk.mongodb.net/?retryWrites=true&w=majority&appName=Nugulbot"
DB_NAME = "NugulBot"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]  # 사용 중인 데이터베이스 이름으로 대체하세요

def delete_comu_data(comu_name: str):
    try:
        # 데이터베이스의 모든 컬렉션 목록을 가져옴
        collections = db.list_collection_names()

        # 각 컬렉션에서 comu_name이 "test_comu"인 문서를 삭제
        for collection_name in collections:
            collection = db[collection_name]
            delete_result = collection.delete_many({"comu_name": comu_name})
            print(f"Deleted {delete_result.deleted_count} documents from {collection_name}")

        print("Deletion complete.")

    except Exception as e:
        print(f"An error occurred: {e}")

# 함수 호출
delete_comu_data("test_comu")
