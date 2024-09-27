from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne, InsertOne, DeleteOne
from pymongo.client_session import ClientSession

class MongoDBManager:
    def __init__(self, uri, db_name):
        self.client = AsyncIOMotorClient(uri)
        self.database = self.client[db_name]

    async def create_one_document(self, session: ClientSession, collection_name: str, data: dict):
        """문서를 생성하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.insert_one(data, session=session)
        return result.inserted_id

    async def create_documents(self, session: ClientSession, collection_name: str, data_list: list):
        """여러 문서를 생성하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.insert_many(data_list, session=session)
        return result.inserted_ids

    async def update_document(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """문서를 업데이트하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.update_one(query, {'$set': new_values}, session=session, upsert=True)
        return result.modified_count, result.upserted_id

    async def update_many_documents(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """여러 문서를 업데이트하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.update_many(query, {'$set': new_values}, session=session)
        return result.modified_count

    async def update_inc_document(self, session: ClientSession, collection_name: str, query: dict, new_values: dict):
        """문서를 업데이트하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.update_many(query, {'$inc': new_values}, session=session, upsert=True)
        return result.modified_count, result.upserted_id

    async def find_documents(self, session: ClientSession, collection_name: str, query: dict):
        """여러 문서를 가져오는 비동기 함수"""
        collection = self.database[collection_name]
        cursor = collection.find(query, session=session)
        documents = []
        async for document in cursor:
            documents.append(document)
        return documents

    async def remove_document(self, session: ClientSession, collection_name: str, query: dict):
        """문서를 제거하는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.delete_many(query, session=session)
        return result.deleted_count

    async def find_one_document(self, session: ClientSession, collection_name: str, query: dict):
        """문서를 가져오는 비동기 함수"""
        collection = self.database[collection_name]
        result = await collection.find_one(query, session=session)
        return result

    async def get_comu_info(self, session: ClientSession, server_id: str):
        """특정 채널의 정보를 가져오는 비동기 함수"""
        collection_name = "community"
        query = {"server_id": server_id}
        result = await self.find_one_document(session, collection_name, query)
        return result