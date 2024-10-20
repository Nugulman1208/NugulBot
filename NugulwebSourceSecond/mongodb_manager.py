from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.client_session import ClientSession

class MongoDBManager:
    def __init__(self, uri: str, db_name: str):
        """MongoDBManager 인스턴스 생성 시 MongoDB 클라이언트를 초기화합니다."""
        self.client = AsyncIOMotorClient(uri)
        self.database = self.client[db_name]

    async def create_one_document(self, session: ClientSession, collection_name: str, data: dict):
        """
        단일 문서를 생성하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param data: 생성할 문서 데이터
        :return: 삽입된 문서의 ID
        """
        collection = self.database[collection_name]
        result = await collection.insert_one(data, session=session)
        return result.inserted_id

    async def create_documents(self, session: ClientSession, collection_name: str, data_list: list):
        """
        여러 문서를 생성하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param data_list: 생성할 여러 문서 데이터
        :return: 삽입된 문서들의 ID 리스트
        """
        collection = self.database[collection_name]
        result = await collection.insert_many(data_list, session=session)
        return result.inserted_ids

    async def update_one_document(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """
        단일 문서를 업데이트하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 업데이트할 문서의 쿼리 조건
        :param new_values: 업데이트할 값
        :return: 수정된 문서의 수와 삽입된 문서의 ID (upsert가 일어난 경우)
        """
        collection = self.database[collection_name]
        result = await collection.update_one(query, {'$set': new_values}, session=session, upsert=True)
        return result.modified_count, result.upserted_id

    async def update_documents(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """
        여러 문서를 업데이트하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 업데이트할 문서의 쿼리 조건
        :param new_values: 업데이트할 값
        :return: 수정된 문서의 수
        """
        collection = self.database[collection_name]
        result = await collection.update_many(query, {'$set': new_values}, session=session, upsert=False)
        return result.modified_count

    async def update_inc_documents(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """
        여러 문서의 특정 필드를 증가시키는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 업데이트할 문서의 쿼리 조건
        :param new_values: 증가시킬 값
        :return: 수정된 문서의 수와 삽입된 문서의 ID (upsert가 일어난 경우)
        """
        collection = self.database[collection_name]
        result = await collection.update_many(query, {'$inc': new_values}, session=session, upsert=True)
        return result.modified_count, result.upserted_id

    async def find_one_document(self, session: ClientSession, collection_name: str, query: dict):
        """
        단일 문서를 가져오는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 검색할 문서의 쿼리 조건
        :return: 검색된 문서
        """
        collection = self.database[collection_name]
        result = await collection.find_one(query, session=session)
        return result

    async def find_documents(self, session: ClientSession, collection_name: str, query: dict):
        """
        여러 문서를 가져오는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 검색할 문서들의 쿼리 조건
        :return: 검색된 문서들의 리스트
        """
        collection = self.database[collection_name]
        cursor = collection.find(query, session=session)
        documents = []
        async for document in cursor:
            documents.append(document)
        return documents

    async def remove_one_document(self, session: ClientSession, collection_name: str, query: dict):
        """
        단일 문서를 삭제하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 삭제할 문서의 쿼리 조건
        :return: 삭제된 문서 수
        """
        collection = self.database[collection_name]
        result = await collection.delete_one(query, session=session)
        return result.deleted_count

    async def remove_documents(self, session: ClientSession, collection_name: str, query: dict):
        """
        여러 문서를 삭제하는 비동기 함수.
        :param session: MongoDB 클라이언트 세션
        :param collection_name: 컬렉션 이름
        :param query: 삭제할 문서들의 쿼리 조건
        :return: 삭제된 문서 수
        """
        collection = self.database[collection_name]
        result = await collection.delete_many(query, session=session)
        return result.deleted_count