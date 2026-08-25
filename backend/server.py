from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class StoryCreate(BaseModel):
    child_name: str
    age: int
    gender: str
    theme: str
    photo_url: Optional[str] = None

class OrderCreate(BaseModel):
    story_id: str
    child_name: str
    format: str
    gift_box: bool = False
    payment_method: str
    customer_name: str
    email: str
    address: str
    city: str
    postal_code: str

class OrderStatusUpdate(BaseModel):
    status: Literal["Order received", "In production", "Shipped"]

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Kids Storybook API", "demo_mode": True}

@api_router.post("/stories")
async def create_story(input: StoryCreate):
    story_id = str(uuid.uuid4())
    story = {
        "id": story_id, "child_name": input.child_name, "age": input.age,
        "gender": input.gender, "theme": input.theme, "photo_url": input.photo_url,
        "title": f"{input.child_name} and the {input.theme.title()} Adventure",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pages": [
            {"page": 1, "text": f"One bright morning, {input.child_name} discovered a tiny door behind the garden gate.", "image": "https://images.unsplash.com/photo-1645113614899-000bdab2bbcf?crop=entropy&cs=srgb&fm=jpg&q=85"},
            {"page": 2, "text": f"With a brave heart and a pocket full of sunshine, {input.child_name} stepped into a {input.theme.lower()} world.", "image": "https://images.unsplash.com/photo-1519764340700-3db40311f21e?crop=entropy&cs=srgb&fm=jpg&q=85"},
            {"page": 3, "text": f"The new friends cheered: “Every great story begins with you, {input.child_name}!”", "image": "https://images.unsplash.com/photo-1707396174323-dd31d3dd4a97?crop=entropy&cs=srgb&fm=jpg&q=85"},
        ], "status": "ready"
    }
    await db.stories.insert_one({**story})
    return story

@api_router.get("/stories")
async def get_stories():
    return await db.stories.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.post("/orders")
async def create_order(input: OrderCreate):
    order = {"id": str(uuid.uuid4()), **input.model_dump(), "status": "Order received", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.orders.insert_one({**order})
    return order

@api_router.get("/orders")
async def get_orders():
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.patch("/orders/{order_id}")
async def update_order(order_id: str, input: OrderStatusUpdate):
    result = await db.orders.update_one({"id": order_id}, {"$set": {"status": input.status}})
    if not result.matched_count:
        raise HTTPException(404, "Order not found")
    return {"id": order_id, "status": input.status}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()