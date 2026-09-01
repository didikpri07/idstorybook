from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Response, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import json
import base64
import hashlib
import hmac
import logging
import asyncio
import httpx
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai import OpenAITextToSpeech
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)
from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

IMAGES_DIR = ROOT_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)
AUDIO_DIR = ROOT_DIR / "generated_audio"
AUDIO_DIR.mkdir(exist_ok=True)


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
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY')
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true'
MIDTRANS_SNAP_HOST = "https://app.midtrans.com" if MIDTRANS_IS_PRODUCTION else "https://app.sandbox.midtrans.com"
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}

# Book prices — defined server-side only, never from frontend
BOOK_PRICES_USD = {"Hardcover": 34.0, "Softcover": 22.0}
BOOK_PRICES_IDR = {"Hardcover": 549000, "Softcover": 359000}

# Visual style → AI illustration prompt descriptor
STYLE_PROMPTS = {
    "Classic Watercolor": (
        "Soft watercolor storybook illustration, hand-painted texture, gentle brushstrokes, "
        "warm pastel palette, delicate translucent color washes, traditional children's picture book art."
    ),
    "3D Animation": (
        "Vibrant 3D animated film still, smooth rounded surfaces, soft subsurface scattering, "
        "cinematic studio lighting, rich saturated colors, Pixar or Illumination movie quality CGI for children."
    ),
    "Comic Book": (
        "Dynamic comic book illustration, bold clean black outlines, vibrant flat cel-shaded colors, "
        "expressive cartoon characters, halftone dot print aesthetic, Marvel Kids panel style, no speech bubbles."
    ),
    "Claymation": (
        "Stop-motion claymation scene, textured polymer clay surfaces, visible handmade fingerprint texture, "
        "vivid saturated colors, charming imperfections, Aardman Animations Wallace and Gromit aesthetic."
    ),
    "Pencil Sketch": (
        "Detailed pencil sketch illustration, fine cross-hatching shading, warm sepia and graphite tones, "
        "hand-drawn expressive line art, classic Quentin Blake or E.H. Shepard children's book style."
    ),
    "Oil Painting": (
        "Rich oil painting illustration, thick impasto brushstrokes, deep jewel-tone colors, "
        "painterly layered texture, dramatic warm lighting, classic storybook art nouveau aesthetic."
    ),
}

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
    visual_style: str = "Classic Watercolor"
    photo_base64: Optional[str] = None  # data URL or raw base64
    story_language: str = "en"
    story_prompt: Optional[str] = None  # Parent's custom story idea / direction


class OrderCreate(BaseModel):
    story_id: str
    child_name: str
    format: str
    gift_box: bool = False
    customer_name: str
    email: str
    address: str
    city: str
    postal_code: str
    country: str = "Other"
    origin_url: str = ""  # frontend sends window.location.origin for Stripe redirect URLs


class OrderStatusUpdate(BaseModel):
    status: Literal["Order received", "In production", "Shipped"]


# ---------- Config ----------
PAGES_PER_BOOK = 24
ILLUSTRATION_COUNT = 8  # unique illustrations, each shared across PAGES_PER_ILLUSTRATION pages
PAGES_PER_ILLUSTRATION = PAGES_PER_BOOK // ILLUSTRATION_COUNT

TEXT_MODEL_PROVIDER = "gemini"
TEXT_MODEL_NAME = "gemini-3-flash-preview"
IMAGE_MODEL_PROVIDER = "gemini"
IMAGE_MODEL_NAME = "gemini-3.1-flash-image-preview"

TTS_MODEL = "tts-1"
TTS_VOICE = "nova"


def _clean_for_tts(text: str) -> str:
    """Strip markdown/URLs so the narrator doesn't read symbols aloud."""
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#>~|`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


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
    child_name: str, age: int, gender: str, theme: str, language: str,
    story_prompt: Optional[str] = None,
) -> dict:
    """Generate a personalized storybook with title and illustration prompts using Gemini."""
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    system_msg = (
        "You are a beloved children's storybook author. You write warm, age-appropriate, "
        "imaginative stories with simple vocabulary and gentle rhythm. Always respond in "
        "valid JSON only, without any prose outside the JSON object."
    )

    # Build optional story direction block
    story_direction_block = ""
    if story_prompt and story_prompt.strip():
        story_direction_block = f"""
Parent's special story idea / direction:
"{story_prompt.strip()}"

Important: Make this the heart of the story. {child_name} should face exactly this situation,
challenge, or topic as the central adventure — resolve it warmly and age-appropriately.
"""

    user_prompt = f"""Write a {PAGES_PER_BOOK}-page personalized children's storybook.

Child details:
- Name: {child_name}
- Age: {age}
- Personality: {gender}
- Theme / World: {theme}
- Language: {lang_name}
{story_direction_block}
Requirements:
- The story must be in {lang_name}.
- Age-appropriate for a {age}-year-old (short sentences, kind tone, no scary content).
- Exactly {PAGES_PER_BOOK} pages. Each page has 1 to 3 short sentences (max ~40 words).
- The child ({child_name}) is the hero. Include friends, a challenge, a discovery, and a happy ending.
- Also produce exactly {ILLUSTRATION_COUNT} short illustration prompts (English, 1-2 sentences each) that describe the key scene for every {PAGES_PER_ILLUSTRATION} pages, in order. Each prompt should describe the setting and action, WITHOUT describing the child's face (a reference photo will handle likeness).

Return ONLY a JSON object exactly like:
{{
  "cover_title": "A unique, poetic title specific to THIS story — evocative and imaginative (e.g. 'Lila and the Lantern Forest' or 'The Night Kai Saved the Stars'). Never a generic title like '{child_name}\\'s Adventure'.",
  "cover_prompt": "A single cinematic, full-page illustration prompt (2–3 English sentences) for the book cover. Capture the emotional peak or most magical moment of the story. Rich atmosphere, vivid lighting, sense of wonder. Do NOT describe the child's face.",
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


async def _illustration_via_google(
    prompt: str,
    photo_b64: Optional[str],
    idx: int,
) -> Optional[str]:
    """Try generating one illustration via Google AI Pro (GEMINI_API_KEY)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    if photo_b64:
        img_bytes_raw = base64.b64decode(photo_b64)
        contents = [
            types.Part.from_bytes(data=img_bytes_raw, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt),
        ]
    else:
        contents = [prompt]

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            raw = part.inline_data.data
            if isinstance(raw, str):
                raw = base64.b64decode(raw)
            filename = f"{uuid.uuid4().hex}.png"
            (IMAGES_DIR / filename).write_bytes(raw)
            return f"/api/images/{filename}"
    return None


async def _illustration_via_emergent(
    prompt: str,
    photo_b64: Optional[str],
    idx: int,
) -> Optional[str]:
    """Generate one illustration via Emergent LLM Key (fallback)."""
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
        data_b64 = images[0].get("data", "")
        img_bytes = base64.b64decode(data_b64)
        filename = f"{uuid.uuid4().hex}.png"
        (IMAGES_DIR / filename).write_bytes(img_bytes)
        return f"/api/images/{filename}"
    return None


async def generate_illustration(
    scene_prompt: str,
    theme: str,
    age: int,
    photo_b64: Optional[str],
    idx: int,
    visual_style: str = "Classic Watercolor",
) -> Optional[str]:
    """Generate one illustration: Google AI Pro first, Emergent LLM Key as fallback."""
    style = STYLE_PROMPTS.get(visual_style, STYLE_PROMPTS["Classic Watercolor"])
    # Append universal children's book safety guard
    style += " Cheerful and safe for kids."
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

    # --- Primary: Google AI Pro ---
    if GEMINI_API_KEY:
        try:
            result = await _illustration_via_google(prompt, photo_b64, idx)
            if result:
                logging.info("Illustration %s generated via Google AI Pro", idx)
                return result
        except Exception as e:
            logging.warning("Google AI illustration %s failed (%s), using Emergent fallback", idx, e)

    # --- Fallback: Emergent LLM Key ---
    try:
        result = await _illustration_via_emergent(prompt, photo_b64, idx)
        if result:
            logging.info("Illustration %s generated via Emergent LLM", idx)
        return result
    except Exception as e:
        logging.exception("Emergent illustration %s also failed: %s", idx, e)
    return None


async def generate_narration(text: str, idx: int) -> Optional[str]:
    """Generate one page of narration via OpenAI TTS; returns served path or None."""
    cleaned = _clean_for_tts(text)
    if not cleaned:
        return None
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        audio_bytes = await tts.generate_speech(
            text=cleaned,
            model=TTS_MODEL,
            voice=TTS_VOICE,
            response_format="mp3",
        )
        filename = f"{uuid.uuid4().hex}.mp3"
        (AUDIO_DIR / filename).write_bytes(audio_bytes)
        return f"/api/audio/{filename}"
    except Exception as e:  # noqa: BLE001
        logging.exception("Narration %s failed: %s", idx, e)
        return None


# ---------- Auth helpers ----------

async def get_current_user(request: Request) -> dict:
    """Validate session token from httpOnly cookie or Authorization header."""
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(401, "Session not found")

    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")

    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def get_optional_user(request: Request) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising 401."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Require the authenticated user to have role='admin'."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


# ---------- Auth endpoints ----------

@api_router.post("/auth/session")
async def auth_session(request: Request, response: Response):
    """Exchange a short-lived session_id from Emergent OAuth for a persistent session."""
    body = await request.json()
    session_id = body.get("session_id", "")
    if not session_id:
        raise HTTPException(400, "session_id required")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
    if resp.status_code != 200:
        logging.error("Emergent auth session-data error %s: %s", resp.status_code, resp.text)
        raise HTTPException(401, "Invalid or expired session_id")

    data = resp.json()
    email = data["email"]
    name = data.get("name", "")
    picture = data.get("picture", "")
    session_token = data["session_token"]

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    role = "admin" if email.lower() in ADMIN_EMAILS else "parent"
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture, "role": role}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": role,
            "created_at": datetime.now(timezone.utc),
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7 * 24 * 3600,
        path="/",
    )

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": user}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie(key="session_token", path="/", samesite="none", secure=True)
    return {"status": "logged out"}


# ---------- Payment helpers ----------

async def _midtrans_snap_token(order_id: str, input: OrderCreate, amount_idr: int) -> dict:
    """Create a Midtrans Snap transaction and return token + redirect_url."""
    item_name = f"IDStorybook – {input.format} ({input.child_name})"[:50]
    payload = {
        "transaction_details": {"order_id": order_id, "gross_amount": amount_idr},
        "customer_details": {"first_name": input.customer_name, "email": input.email},
        "item_details": [{"id": input.format.lower(), "price": amount_idr, "quantity": 1, "name": item_name}],
        "callbacks": {"finish": f"{input.origin_url}/checkout/success?order_id={order_id}"},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{MIDTRANS_SNAP_HOST}/snap/v1/transactions",
            json=payload,
            auth=(MIDTRANS_SERVER_KEY, ""),
            headers={"Accept": "application/json"},
        )
    if resp.status_code not in (200, 201):
        logging.error("Midtrans Snap error %s: %s", resp.status_code, resp.text)
        raise HTTPException(502, "Payment service temporarily unavailable. Please try again.")
    result = resp.json()
    return {"snap_token": result["token"], "redirect_url": result.get("redirect_url", "")}


async def _stripe_checkout_session(order_id: str, input: OrderCreate, amount_usd: float) -> dict:
    """Create a Stripe Checkout session and return url + session_id."""
    origin = input.origin_url.rstrip("/") or "https://localhost:3000"
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}"
    cancel_url = f"{origin}/checkout/cancel?order_id={order_id}"

    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY,
        webhook_url=f"{origin}/api/webhook/stripe",
    )
    req = CheckoutSessionRequest(
        amount=amount_usd,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": order_id, "child_name": input.child_name, "format": input.format},
    )
    session = await stripe_checkout.create_checkout_session(req)
    return {"checkout_url": session.url, "session_id": session.session_id}


# ---------- Background generation ----------

async def run_story_generation(story_id: str, input: StoryCreate, photo_b64: Optional[str]):
    """Background task: run full AI generation pipeline and update the story document when done."""
    try:
        story_data = await generate_story_text(
            input.child_name, input.age, input.gender, input.theme, input.story_language,
            story_prompt=input.story_prompt,
        )
    except Exception as e:
        logging.exception("Background story text generation failed for %s", story_id)
        err_msg = str(e)
        if "budget" in err_msg.lower() or "quota" in err_msg.lower():
            err_msg = "AI credit budget exceeded. Please top up your Emergent LLM key balance."
        await db.stories.update_one(
            {"id": story_id},
            {"$set": {"status": "failed", "error": err_msg[:500]}}
        )
        return

    # Extract cover data from LLM response (with sensible fallbacks)
    cover_title = (story_data.get("cover_title") or story_data["title"]).strip()
    cover_prompt_text = (story_data.get("cover_prompt") or story_data["illustration_prompts"][0]).strip()

    # Generate cover illustration + all story illustrations in one parallel batch
    cover_task = generate_illustration(
        scene_prompt=cover_prompt_text,
        theme=input.theme,
        age=input.age,
        photo_b64=photo_b64,
        idx=ILLUSTRATION_COUNT,      # unique idx so filename doesn't clash
        visual_style=input.visual_style,
    )
    illustration_tasks = [cover_task] + [
        generate_illustration(
            scene_prompt=prompt,
            theme=input.theme,
            age=input.age,
            photo_b64=photo_b64,
            idx=i,
            visual_style=input.visual_style,
        )
        for i, prompt in enumerate(story_data["illustration_prompts"])
    ]
    all_results = await asyncio.gather(*illustration_tasks)
    cover_img = all_results[0] or PLACEHOLDER_IMAGE
    illustrations_raw = all_results[1:]
    illustrations_generated = sum(1 for img in illustrations_raw if img)
    illustrations = [img or PLACEHOLDER_IMAGE for img in illustrations_raw]

    async def _batched_narration(texts: List[str]) -> List[Optional[str]]:
        batch_size = 8
        results: List[Optional[str]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            results.extend(await asyncio.gather(*[
                generate_narration(text, start + i) for i, text in enumerate(batch)
            ]))
        return results

    page_texts = [p["text"] for p in story_data["pages"]]
    audio_paths = await _batched_narration(page_texts)
    narrations_generated = sum(1 for a in audio_paths if a)

    pages = []
    for i, page in enumerate(story_data["pages"]):
        illus_idx = min(i // PAGES_PER_ILLUSTRATION, len(illustrations) - 1)
        pages.append({
            "page": i + 1,
            "text": page["text"],
            "image": illustrations[illus_idx],
            "audio": audio_paths[i],
        })

    await db.stories.update_one(
        {"id": story_id},
        {"$set": {
            "title": story_data["title"],
            "cover": {
                "title": cover_title,
                "image": cover_img,
            },
            "pages": pages,
            "cover_image": cover_img,
            "illustrations_generated": illustrations_generated,
            "illustrations_expected": ILLUSTRATION_COUNT,
            "narrations_generated": narrations_generated,
            "narrations_expected": len(page_texts),
            "status": "completed",
        }}
    )
    logging.info("Background story generation completed for %s", story_id)


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "IDStorybook API", "ai_enabled": bool(EMERGENT_LLM_KEY)}

@api_router.post("/stories")
async def create_story(input: StoryCreate, background_tasks: BackgroundTasks, request: Request):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured on the server")
    user = await get_optional_user(request)

    photo_b64 = _strip_data_url(input.photo_base64)
    story_id = str(uuid.uuid4())

    story = {
        "id": story_id,
        "user_id": user["user_id"] if user else None,
        "child_name": input.child_name,
        "age": input.age,
        "gender": input.gender,
        "theme": input.theme,
        "visual_style": input.visual_style,
        "story_language": input.story_language,
        "story_prompt": input.story_prompt or None,
        "title": f"{input.child_name}'s Story",
        "pages": [],
        "cover_image": PLACEHOLDER_IMAGE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "narrator_voice": TTS_VOICE,
        "status": "processing",
    }
    await db.stories.insert_one({**story})
    background_tasks.add_task(run_story_generation, story_id, input, photo_b64)
    return story


@api_router.get("/stories")
async def get_stories(user: dict = Depends(get_current_user)):
    """Lightweight list: only fetch lightweight fields, skip the heavy pages payload."""
    projection = {
        "_id": 0, "id": 1, "child_name": 1, "age": 1, "gender": 1, "theme": 1,
        "story_language": 1, "title": 1, "cover_image": 1, "created_at": 1,
        "pages.image": 1,
    }
    stories = await db.stories.find({"user_id": user["user_id"]}, projection).sort("created_at", -1).to_list(100)
    lite = []
    for s in stories:
        pages = s.get("pages") or []
        cover = s.get("cover_image") or (pages[0].get("image") if pages else None)
        lite.append({
            "id": s.get("id"),
            "child_name": s.get("child_name"),
            "age": s.get("age"),
            "gender": s.get("gender"),
            "theme": s.get("theme"),
            "story_language": s.get("story_language", "en"),
            "title": s.get("title"),
            "cover_image": cover,
            "page_count": len(pages),
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
async def create_order(input: OrderCreate, request: Request):
    user = await get_optional_user(request)
    order_id = str(uuid.uuid4())
    is_indonesia = input.country.strip().lower() in ("indonesia", "id")
    gateway = "midtrans" if is_indonesia else "stripe"

    order = {
        "id": order_id,
        "user_id": user["user_id"] if user else None,
        "story_id": input.story_id,
        "child_name": input.child_name,
        "format": input.format,
        "gift_box": input.gift_box,
        "customer_name": input.customer_name,
        "email": input.email,
        "address": input.address,
        "city": input.city,
        "postal_code": input.postal_code,
        "country": input.country,
        "status": "Order received",
        "payment_status": "pending",
        "payment_gateway": gateway,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.orders.insert_one({**order})

    payment_data: dict = {}
    try:
        if is_indonesia:
            amount_idr = BOOK_PRICES_IDR.get(input.format, BOOK_PRICES_IDR["Hardcover"])
            payment_data = await _midtrans_snap_token(order_id, input, amount_idr)
        else:
            amount_usd = BOOK_PRICES_USD.get(input.format, BOOK_PRICES_USD["Hardcover"])
            payment_data = await _stripe_checkout_session(order_id, input, amount_usd)
            await db.orders.update_one(
                {"id": order_id},
                {"$set": {"payment_session_id": payment_data["session_id"]}},
            )
    except HTTPException:
        raise
    except Exception:
        logging.exception("Payment session creation failed for order %s", order_id)
        await db.orders.delete_one({"id": order_id})
        raise HTTPException(502, "Could not start checkout. Please try again.")

    return {**order, "gateway": gateway, **payment_data}


@api_router.get("/orders")
async def get_orders(user: dict = Depends(get_current_user)):
    """Return orders for the authenticated user."""
    return await db.orders.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.get("/admin/orders")
async def get_admin_orders(user: dict = Depends(get_admin_user)):
    """Admin view: all orders regardless of owner."""
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.patch("/orders/{order_id}")
async def update_order(order_id: str, input: OrderStatusUpdate, user: dict = Depends(get_admin_user)):
    result = await db.orders.update_one({"id": order_id}, {"$set": {"status": input.status}})
    if not result.matched_count:
        raise HTTPException(404, "Order not found")
    return {"id": order_id, "status": input.status}


# ---------- Stripe webhook (Flow B) ----------
@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY)
    try:
        event = await stripe_checkout.handle_webhook(body, sig)
    except Exception:
        logging.exception("Stripe webhook handling error")
        raise HTTPException(400, "Invalid webhook payload")

    if event.payment_status == "paid":
        order_id = (event.metadata or {}).get("order_id", "")
        if order_id:
            await db.orders.update_one(
                {"id": order_id, "payment_status": {"$ne": "paid"}},
                {"$set": {
                    "payment_status": "paid",
                    "payment_session_id": event.session_id,
                    "status": "Order received",
                }},
            )
    return {"status": "ok"}


# ---------- Midtrans notification ----------
@api_router.post("/payments/midtrans/notification")
async def midtrans_notification(request: Request):
    n = await request.json()

    # Validate signature: sha512(order_id + status_code + gross_amount + server_key)
    raw = f"{n.get('order_id')}{n.get('status_code')}{n.get('gross_amount')}{MIDTRANS_SERVER_KEY}"
    expected = hashlib.sha512(raw.encode()).hexdigest()
    if not hmac.compare_digest(expected, n.get("signature_key", "")):
        raise HTTPException(403, "Invalid notification signature")

    order_id = n.get("order_id", "")
    txn_status = n.get("transaction_status", "")
    fraud_status = (n.get("fraud_status") or "").lower()

    if txn_status == "settlement" or (txn_status == "capture" and fraud_status in ("", "accept")):
        new_status = "paid"
    elif txn_status == "pending":
        new_status = "pending"
    elif txn_status in ("cancel", "deny", "expire"):
        new_status = "failed"
    else:
        new_status = "pending"

    # Only advance status (paid/failed cannot be downgraded to pending)
    RANK = {"pending": 0, "paid": 10, "failed": 10}
    order = await db.orders.find_one({"id": order_id}, {"payment_status": 1})
    if order and RANK.get(new_status, 0) >= RANK.get(order.get("payment_status", "pending"), 0):
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"payment_status": new_status}},
        )
    return {"status": "ok"}


# ---------- Payment status polling ----------
@api_router.get("/payments/status/{order_id}")
async def get_payment_status(order_id: str):
    order = await db.orders.find_one(
        {"id": order_id},
        {"_id": 0, "id": 1, "payment_status": 1, "status": 1, "payment_gateway": 1},
    )
    if not order:
        raise HTTPException(404, "Order not found")
    return order


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
# Serve narration audio as static files
app.mount("/api/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    from pymongo.errors import OperationFailure
    await db.users.create_index("email", unique=True)
    await db.user_sessions.create_index("session_token")
    # Recreate expires_at index without TTL if an old TTL version exists
    try:
        await db.user_sessions.create_index("expires_at")
    except OperationFailure:
        await db.user_sessions.drop_index("expires_at_1")
        await db.user_sessions.create_index("expires_at")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
