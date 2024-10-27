from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
import redis
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MONGO_INITDB_ROOT_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME")
MONGO_INITDB_ROOT_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

# Connection URI
MONGO_URI = f"mongodb://{MONGO_INITDB_ROOT_USERNAME}:{MONGO_INITDB_ROOT_PASSWORD}@localhost:27077"

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust according to your requirements
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = redis.Redis(host='localhost', port=6479, db=0)
client = AsyncIOMotorClient(MONGO_URI)
db = client['quiz_db']
users_collection = db['users']

class Quiz(BaseModel):
    quiz_id: str

class ScoreUpdate(BaseModel):
    user_id: str
    score: int

@app.get("/test-mongodb/")
async def test_mongodb():
    try:
        # Test MongoDB connection by fetching databases
        databases = await client.list_database_names()
        return {"status": "Connected to MongoDB", "databases": databases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB connection error: {str(e)}")

@app.get("/test-redis/")
def test_redis():
    try:
        # Test Redis connection by setting and getting a value
        redis_client.set("test_key", "test_value")
        value = redis_client.get("test_key").decode("utf-8")
        return {"status": "Connected to Redis", "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis connection error: {str(e)}")

@app.post("/join-quiz/")
async def join_quiz(quiz: Quiz):
    return {"message": f"Joined quiz {quiz.quiz_id}"}

@app.websocket("/ws/{quiz_id}")
async def websocket_endpoint(websocket: WebSocket, quiz_id: str):
    user_id = websocket.query_params.get('user_id')
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message['type'] == 'score_update':
                await update_score(message['user_id'], message['score'], quiz_id)
                await update_leaderboard(websocket, quiz_id)
    except WebSocketDisconnect:
        print(f"Client {user_id} disconnected")

async def update_score(user_id: str, score: int, quiz_id: str):
    # Update score in MongoDB
    await users_collection.update_one(
        {"user_id": user_id, "quiz_id": quiz_id},
        {"$set": {"score": score, "quiz_id": quiz_id}},
        upsert=True
    )
    # Update score in Redis, specific to quiz_id
    redis_key = f'leaderboard_{quiz_id}'
    redis_client.zadd(redis_key, {user_id: score})

def serialize_object_id(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError("Object of type ObjectId is not JSON serializable")

async def update_leaderboard(websocket: WebSocket, quiz_id: str):
    redis_key = f'leaderboard_{quiz_id}'
    leaderboard = redis_client.zrangebyscore(redis_key, '-inf', '+inf', withscores=True, score_cast_func=int)
    leaderboard_serializable = []
    for rank, user in enumerate(leaderboard, start=1):
        leaderboard_serializable.append({"user_id": user[0].decode('utf-8'), "score": user[1], "rank": rank})
    await websocket.send_text(json.dumps({"type": "leaderboard_update", "data": leaderboard_serializable}))
