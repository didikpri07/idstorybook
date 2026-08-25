from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import json
import base64
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

IMAGES_DIR = ROOT_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)


def _ensure_placeholder() -> str:
    """Create a warm pastel placeholder illustration once and return its served path."""
    filename = "placeholder.png"
    path = IMAGES_DIR / filename
    if not path.exists():
        img = Image.new("RGB", (900, 600), (255, 236, 214))
        draw = ImageDraw.Draw(img)
        for i, y in enumerate(range(0, 600, 30)):
            shade = 250 - i * 2
            draw.rectangle([(0, y), (900, y + 15)], fill=(shade, 224, 205))
        draw.ellipse((350, 200, 550, 400), fill=(255, 205, 165))
        draw.text((280, 500), "Illustration coming soon", fill=(140, 90, 70))
        img.save(path, "PNG")
    return f"/api/images/{filename}"


PLACEHOLDER_IMAGE = _ensure_placeholder()

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# ---------- Models ----------
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
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
    photo_base64: Optional[str] = None  # data URL or raw base64
    story_language: str = "en"


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


# ---------- Config ----------
PAGES_PER_BOOK = 32
ILLUSTRATION_COUNT = 8  # unique illustrations, each shared across 4 consecutive pages
PAGES_PER_ILLUSTRATION = PAGES_PER_BOOK // ILLUSTRATION_COUNT

TEXT_MODEL_PROVIDER = "gemini"
TEXT_MODEL_NAME = "gemini-3-flash-preview"
IMAGE_MODEL_PROVIDER = "gemini"
IMAGE_MODEL_NAME = "gemini-3.1-flash-image-preview"


# ---------- AI Helpers ----------
def _strip_data_url(data: Optional[str]) -> Optional[str]:
    """Return raw base64 payload from a data URL or None."""
    if not data:
        return None
    if data.startswith("data:") and "," in data:
        return data.split(",", 1)[1]
    return data


def _parse_json_from_text(text: str) -> dict:
    """Extract JSON object from LLM text response (handles ```json fences)."""
    if not text:
        raise ValueError("Empty LLM response")
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group(0))


async def generate_story_text(
    child_name: str, age: int, gender: str, theme: str, language: str
) -> dict:
    """Generate a 32-page storybook with title and 8 illustration prompts using Gemini."""
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    system_msg = (
        "You are a beloved children's storybook author. You write warm, age-appropriate, "
        "imaginative stories with simple vocabulary and gentle rhythm. Always respond in "
        "valid JSON only, without any prose outside the JSON object."
    )
    user_prompt = f"""Write a {PAGES_PER_BOOK}-page personalized children's storybook.

Child details:
- Name: {child_name}
- Age: {age}
- Personality: {gender}
- Theme / World: {theme}
- Language: {lang_name}

Requirements:
- The story must be in {lang_name}.
- Age-appropriate for a {age}-year-old (short sentences, kind tone, no scary content).
- Exactly {PAGES_PER_BOOK} pages. Each page has 1 to 3 short sentences (max ~40 words).
- The child ({child_name}) is the hero. Include friends, a challenge, a discovery, and a happy ending.
- Also produce exactly {ILLUSTRATION_COUNT} short illustration prompts (English, 1-2 sentences each) that describe the key scene for every {PAGES_PER_ILLUSTRATION} pages, in order. Each prompt should describe the setting and action, WITHOUT describing the child's face (a reference photo will handle likeness).

Return ONLY a JSON object exactly like:
{{
  "title": "...",
  "illustration_prompts": ["scene 1", "scene 2", ..., "scene {ILLUSTRATION_COUNT}"],
  "pages": [
    {{"page": 1, "text": "..."}},
    {{"page": 2, "text": "..."}}
    // ... {PAGES_PER_BOOK} entries total
  ]
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"story-{uuid.uuid4()}",
        system_message=system_msg,
    ).with_model(TEXT_MODEL_PROVIDER, TEXT_MODEL_NAME)

    response = await chat.send_message(UserMessage(text=user_prompt))
    data = _parse_json_from_text(response if isinstance(response, str) else str(response))

    if "pages" not in data or "title" not in data:
        raise ValueError("Story JSON missing required keys")

    # Normalize
    pages = data["pages"][:PAGES_PER_BOOK]
    while len(pages) < PAGES_PER_BOOK:
        pages.append({"page": len(pages) + 1, "text": f"{child_name} smiled and the adventure continued."})
    data["pages"] = [{"page": i + 1, "text": (p.get("text") or "").strip()} for i, p in enumerate(pages)]

    prompts = data.get("illustration_prompts", [])[:ILLUSTRATION_COUNT]
    while len(prompts) < ILLUSTRATION_COUNT:
        prompts.append(f"A whimsical {theme.lower()} scene with a happy child hero.")
    data["illustration_prompts"] = prompts

    return data


async def generate_illustration(
    scene_prompt: str,
    theme: str,
    age: int,
    photo_b64: Optional[str],
    idx: int,
) -> Optional[str]:
    """Generate one illustration and return a data URL, or None on failure."""
    style = (
        "Soft watercolor children's storybook illustration, warm pastel palette, "
        "gentle lighting, whimsical, hand-painted texture, cheerful and safe for kids."
    )
    reference_note = (
        " Draw the main child character as an illustrated storybook version of the child in "
        "the reference photo, keeping recognisable features like hair color/style and skin tone. "
        "Do NOT reproduce a photorealistic face — stylize as a cartoon character."
        if photo_b64
        else f" The main child character is around {age} years old with a friendly, curious face."
    )
    prompt = (
        f"{style} Scene: {scene_prompt} Theme: {theme}.{reference_note} "
        "Full illustration, no text, no letters, no watermarks. Landscape composition."
    )

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"img-{uuid.uuid4()}",
            system_message="You are an illustrator for children's storybooks.",
        ).with_model(IMAGE_MODEL_PROVIDER, IMAGE_MODEL_NAME).with_params(
            modalities=["image", "text"]
        )

        file_contents = [ImageContent(photo_b64)] if photo_b64 else None
        msg = UserMessage(text=prompt, file_contents=file_contents) if file_contents else UserMessage(text=prompt)
        _, images = await chat.send_message_multimodal_response(msg)

        if images:
            img = images[0]
            data_b64 = img.get("data", "")
            img_bytes = base64.b64decode(data_b64)
            filename = f"{uuid.uuid4().hex}.png"
            file_path = IMAGES_DIR / filename
            file_path.write_bytes(img_bytes)
            return f"/api/images/{filename}"
    except Exception as e:  # noqa: BLE001
        logging.exception("Illustration %s failed: %s", idx, e)
    return None


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "Kids Storybook API", "ai_enabled": bool(EMERGENT_LLM_KEY)}


@api_router.post("/stories")
async def create_story(input: StoryCreate):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured on the server")

    photo_b64 = _strip_data_url(input.photo_base64)

    try:
        story_data = await generate_story_text(
            input.child_name, input.age, input.gender, input.theme, input.story_language
        )
    except Exception as e:  # noqa: BLE001
        logging.exception("Story text generation failed")
        message = str(e)
        if "budget" in message.lower() or "quota" in message.lower():
            detail = "AI credit budget exceeded. Please top up your Emergent LLM key balance."
        else:
            detail = "Story generation is temporarily unavailable. Please try again shortly."
        raise HTTPException(502, detail) from e

    # Generate all illustrations in parallel (small enough set to be safe)
    illustration_tasks = [
        generate_illustration(
            scene_prompt=prompt,
            theme=input.theme,
            age=input.age,
            photo_b64=photo_b64,
            idx=i,
        )
        for i, prompt in enumerate(story_data["illustration_prompts"])
    ]
    illustrations_raw = await asyncio.gather(*illustration_tasks)
    illustrations_generated = sum(1 for img in illustrations_raw if img)
    illustrations = [img or PLACEHOLDER_IMAGE for img in illustrations_raw]

    # Map each page to its illustration (every PAGES_PER_ILLUSTRATION pages share one)
    pages = []
    for i, page in enumerate(story_data["pages"]):
        illus_idx = min(i // PAGES_PER_ILLUSTRATION, len(illustrations) - 1)
        pages.append({
            "page": i + 1,
            "text": page["text"],
            "image": illustrations[illus_idx],
        })

    story_id = str(uuid.uuid4())
    story = {
        "id": story_id,
        "child_name": input.child_name,
        "age": input.age,
        "gender": input.gender,
        "theme": input.theme,
        "story_language": input.story_language,
        "title": story_data["title"],
        "pages": pages,
        "cover_image": illustrations[0],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "illustrations_generated": illustrations_generated,
        "illustrations_expected": ILLUSTRATION_COUNT,
        "status": "ready" if illustrations_generated == ILLUSTRATION_COUNT else "partial",
    }
    await db.stories.insert_one({**story})
    # Return without the heavy pages payload duplicated (still returns full)
    return story


@api_router.get("/stories")
async def get_stories():
    """Lightweight list: strip base64 image data from pages, keep cover only."""
    stories = await db.stories.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    lite = []
    for s in stories:
        cover = s.get("cover_image") or (s.get("pages") or [{}])[0].get("image")
        lite.append({
            "id": s.get("id"),
            "child_name": s.get("child_name"),
            "age": s.get("age"),
            "gender": s.get("gender"),
            "theme": s.get("theme"),
            "story_language": s.get("story_language", "en"),
            "title": s.get("title"),
            "cover_image": cover,
            "page_count": len(s.get("pages") or []),
            "created_at": s.get("created_at"),
        })
    return lite


@api_router.get("/stories/{story_id}")
async def get_story(story_id: str):
    story = await db.stories.find_one({"id": story_id}, {"_id": 0})
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@api_router.post("/orders")
async def create_order(input: OrderCreate):
    order = {
        "id": str(uuid.uuid4()),
        **input.model_dump(),
        "status": "Order received",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
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
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    _ = await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks


# Include the router in the main app
app.include_router(api_router)

# Serve generated illustrations as static files
app.mount("/api/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
