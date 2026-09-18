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
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai import OpenAITextToSpeech
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)
from PIL import Image, ImageDraw
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from accounts import router as accounts_router, UserPublic, digest, claim_guest_stories
import accounts
from generation import generate as generate_with_progress, GOOGLE_VOICES, progress_of
from story_access import authorized_story, public_story
from story_models import StoryPublic, StoryProgress, OrderPublic
from audio_routes import router as audio_router
import secrets


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
from database import client, db

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY')
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true'
MIDTRANS_SNAP_HOST = "https://app.midtrans.com" if MIDTRANS_IS_PRODUCTION else "https://app.sandbox.midtrans.com"
FRONTEND_URL = os.environ['FRONTEND_URL']
TRUSTED_FRONTEND_ORIGINS = os.environ['TRUSTED_FRONTEND_ORIGINS'].split(',')
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
    child_name: str = Field(min_length=1, max_length=80)
    age: int = Field(ge=3, le=10)
    gender: str = Field(min_length=1, max_length=80)
    theme: str = Field(min_length=1, max_length=100)
    visual_style: str = "Classic Watercolor"
    photo_base64: Optional[str] = Field(default=None, max_length=14000000)
    story_language: Literal['en', 'id'] = "en"
    story_prompt: Optional[str] = Field(default=None, max_length=300)
    page_count: int = 24  # 8, 16, 24, or 32
    voice_id: Literal['nova', 'onyx', 'shimmer'] = 'nova'

    @field_validator("page_count")
    @classmethod
    def _valid_page_count(cls, v):
        if v not in (8, 16, 24, 32):
            raise ValueError('Choose 8, 16, 24, or 32 pages')
        return v


class OrderCreate(BaseModel):
    story_id: str
    child_name: str
    format: Literal['Hardcover', 'Softcover']
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
PAGES_PER_BOOK = 24            # default book length
PAGES_PER_ILLUSTRATION = 1     # one unique illustration per page
ILLUSTRATION_COUNT = PAGES_PER_BOOK // PAGES_PER_ILLUSTRATION

TEXT_MODEL_PROVIDER = "gemini"
TEXT_MODEL_NAME = os.environ['GEMINI_TEXT_MODEL']
IMAGE_MODEL_PROVIDER = "gemini"
IMAGE_MODEL_NAME = os.environ['GEMINI_IMAGE_MODEL']

TTS_MODEL = "tts-1"
TTS_VOICE = "nova"


def _clean_for_tts(text: str) -> str:
    """Strip markdown/URLs and normalize punctuation so the narrator reads evenly."""
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#>~|`]", "", text)
    # Soften excited punctuation → calmer, more consistent narrator tone
    text = re.sub(r"!+", ".", text)          # exclamation → period (calmer prosody)
    text = re.sub(r"\.{2,}", ",", text)      # ellipsis → comma (brief pause, not trailing off)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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
    story_prompt: Optional[str] = None, page_count: int = PAGES_PER_BOOK,
) -> dict:
    """Generate a personalized storybook with title and illustration prompts.
    Primary: Google AI via GEMINI_API_KEY. Fallback: Emergent LLM Key."""
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    # Dynamic sizing: one unique illustration per PAGES_PER_ILLUSTRATION pages.
    pages_per_book = page_count
    illustration_count = (page_count + PAGES_PER_ILLUSTRATION - 1) // PAGES_PER_ILLUSTRATION
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

    user_prompt = f"""Write a {pages_per_book}-page personalized children's storybook.

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
- Exactly {pages_per_book} pages. Each page has 1 to 3 short sentences (max ~40 words).
- The child ({child_name}) is the hero. Include friends, a challenge, a discovery, and a happy ending.
- Pace the plot so it arcs naturally across all {pages_per_book} pages.
- Also produce exactly {illustration_count} short illustration prompts (English, 1-2 sentences each) — ONE for each page, describing that page's key scene, in order. Each prompt should describe the setting and action, WITHOUT describing the child's face (a reference photo will handle likeness).

Return ONLY a JSON object exactly like:
{{
  "cover_title": "A unique, poetic title specific to THIS story — evocative and imaginative (e.g. 'Lila and the Lantern Forest' or 'The Night Kai Saved the Stars'). Never a generic title like '{child_name}\\'s Adventure'.",
  "cover_prompt": "A single cinematic, full-page illustration prompt (2–3 English sentences) for the book cover. Capture the emotional peak or most magical moment of the story. Rich atmosphere, vivid lighting, sense of wonder. Do NOT describe the child's face.",
  "title": "...",
  "illustration_prompts": ["scene 1", "scene 2", ..., "scene {illustration_count}"],
  "pages": [
    {{"page": 1, "text": "..."}},
    {{"page": 2, "text": "..."}}
    // ... {pages_per_book} entries total
  ]
}}"""

    raw_text = None

    # --- Primary: Google AI via GEMINI_API_KEY ---
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types as gtypes
            gclient = genai.Client(api_key=GEMINI_API_KEY)
            response = await gclient.aio.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=[user_prompt],
                config=gtypes.GenerateContentConfig(system_instruction=system_msg),
            )
            raw_text = response.text
            logging.info("Story text generated via Google AI (GEMINI_API_KEY)")
        except Exception as e:
            logging.warning("Google AI story text failed (%s)", type(e).__name__)
            if not EMERGENT_LLM_KEY:
                raise

    # --- Fallback: Emergent LLM Key ---
    if raw_text is None:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"story-{uuid.uuid4()}",
            system_message=system_msg,
        ).with_model(TEXT_MODEL_PROVIDER, TEXT_MODEL_NAME)
        response = await chat.send_message(UserMessage(text=user_prompt))
        raw_text = response if isinstance(response, str) else str(response)
        logging.info("Story text generated via Emergent LLM Key (fallback)")

    data = _parse_json_from_text(raw_text)

    if "pages" not in data or "title" not in data:
        raise ValueError("Story JSON missing required keys")

    # Normalize
    pages = data["pages"][:pages_per_book]
    if len(pages) != pages_per_book or any(not p.get('text', '').strip() for p in pages):
        raise ValueError('Story text did not contain the requested complete pages')
    data["pages"] = [{"page": i + 1, "text": (p.get("text") or "").strip()} for i, p in enumerate(pages)]

    prompts = data.get("illustration_prompts", [])[:illustration_count]
    while len(prompts) < illustration_count:
        prompts.append(f"A whimsical {theme.lower()} scene with a happy child hero.")
    data["illustration_prompts"] = prompts

    return data


async def _illustration_via_google(
    prompt: str,
    photo_b64: Optional[str],
    idx: int,
) -> Optional[bytes]:
    """Try generating one illustration via Google AI Pro (GEMINI_API_KEY). Returns raw image bytes."""
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
        model=IMAGE_MODEL_NAME,
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
            return raw
    return None


async def _illustration_via_emergent(
    prompt: str,
    photo_b64: Optional[str],
    idx: int,
) -> Optional[bytes]:
    """Generate one illustration via Emergent LLM Key (fallback). Returns raw image bytes."""
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
        return base64.b64decode(data_b64)
    return None


def _normalize_illustration(raw_bytes: bytes, target_w: int = 1024, target_h: int = 640) -> bytes:
    """Resize and compress illustration to a consistent landscape JPEG (~100KB vs ~900KB PNG)."""
    from io import BytesIO
    from PIL import ImageOps
    img = Image.open(BytesIO(raw_bytes)).convert("RGB")
    img = ImageOps.fit(img, (target_w, target_h), method=Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue()


async def generate_illustration(
    scene_prompt: str,
    theme: str,
    age: int,
    photo_b64: Optional[str],
    idx: int,
    visual_style: str = "Classic Watercolor",
) -> Optional[str]:
    """Generate one illustration: Google AI Pro first, Emergent LLM Key as fallback.
    All illustrations are normalized to 1024×640 JPEG for consistent size and fast loading."""
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

    raw_bytes: Optional[bytes] = None

    # --- Primary: Google AI Pro ---
    if GEMINI_API_KEY:
        try:
            raw_bytes = await _illustration_via_google(prompt, photo_b64, idx)
            if raw_bytes:
                logging.info("Illustration %s generated via Google AI Pro", idx)
        except Exception as e:
            logging.warning("Google AI illustration %s failed (%s)", idx, type(e).__name__)

    # --- Fallback: Emergent LLM Key ---
    if not raw_bytes and EMERGENT_LLM_KEY:
        try:
            raw_bytes = await _illustration_via_emergent(prompt, photo_b64, idx)
            if raw_bytes:
                logging.info("Illustration %s generated via Emergent LLM", idx)
        except Exception as e:
            logging.warning("Illustration %s fallback failed (%s)", idx, type(e).__name__)

    if not raw_bytes:
        return None

    # Normalize to consistent 1024×640 JPEG regardless of source dimensions
    try:
        normalized = _normalize_illustration(raw_bytes)
    except Exception as e:
        logging.warning("Illustration %s normalization failed (%s), saving raw bytes", idx, e)
        normalized = raw_bytes

    filename = f"{uuid.uuid4().hex}.jpg"
    (IMAGES_DIR / filename).write_bytes(normalized)
    return f"/api/images/{filename}"


async def generate_narration(text: str, idx: int, language: str = "en", voice_id: str = 'nova') -> Optional[str]:
    """Generate one page of narration. Primary: Google TTS (Achernar). Fallback: OpenAI TTS.
    language: 'en' or 'id' — sets the style instruction language for consistent warm tone."""
    cleaned = _clean_for_tts(text)
    if not cleaned:
        return None

    # Style instruction prepended to guide tone without being narrated
    style_instruction = (
        "Bacakan dengan nada hangat dan ramah."
        if language == "id"
        else "Read aloud in a warm, welcoming tone."
    )
    tts_content = f"{style_instruction}\n\n{cleaned}"

    # --- Primary: Google Gemini TTS (Achernar voice) ---
    if GEMINI_API_KEY:
        try:
            import wave, io
            from google import genai
            from google.genai import types as gtypes
            gclient = genai.Client(api_key=GEMINI_API_KEY)
            resp = await gclient.aio.models.generate_content(
                model=os.environ['GEMINI_TTS_MODEL'],
                contents=tts_content,
                config=gtypes.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=gtypes.SpeechConfig(
                        voice_config=gtypes.VoiceConfig(
                            prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name=GOOGLE_VOICES[voice_id])
                        )
                    ),
                ),
            )
            pcm_bytes = resp.candidates[0].content.parts[0].inline_data.data
            # Guard against empty/corrupt audio
            if not pcm_bytes or len(pcm_bytes) < 512:
                raise ValueError(f"Google TTS returned suspiciously small audio ({len(pcm_bytes or b'')} bytes)")
            # Wrap raw L16 PCM in a proper WAV container
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)       # 16-bit
                wf.setframerate(24000)
                wf.writeframes(pcm_bytes)
            filename = f"{uuid.uuid4().hex}.wav"
            (AUDIO_DIR / filename).write_bytes(buf.getvalue())
            logging.info("Narration %s generated via Google TTS (%s, lang=%s)", idx, GOOGLE_VOICES[voice_id], language)
            return f"/api/audio/{filename}"
        except Exception as e:
            logging.warning("Google TTS narration %s failed (%s)", idx, type(e).__name__)

    # --- Fallback: OpenAI TTS via Emergent LLM Key (uses cleaned text only, no style prefix) ---
    if not EMERGENT_LLM_KEY:
        return None
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        audio_bytes = await tts.generate_speech(
            text=cleaned,
            model=TTS_MODEL,
            voice=voice_id,
            response_format="mp3",
        )
        filename = f"{uuid.uuid4().hex}.mp3"
        (AUDIO_DIR / filename).write_bytes(audio_bytes)
        logging.info("Narration %s generated via OpenAI TTS (fallback)", idx)
        return f"/api/audio/{filename}"
    except Exception as e:
        logging.warning("Narration %s failed on all providers (%s)", idx, type(e).__name__)
    return None


# ---------- Auth helpers ----------

async def get_current_user(request: Request) -> dict:
    return await accounts.get_current_user(request)


async def get_optional_user(request: Request) -> Optional[dict]:
    return await accounts.get_optional_user(request)


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
    await claim_guest_stories(request, user_id)
    return {"user": UserPublic(**user)}


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
    origin = FRONTEND_URL.rstrip('/')
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
    await generate_with_progress(story_id, generate_story_text, generate_illustration, generate_narration, AUDIO_DIR)


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "IDStorybook API", "ai_enabled": bool(GEMINI_API_KEY or EMERGENT_LLM_KEY)}

@api_router.post("/stories", response_model=StoryPublic, status_code=202)
async def create_story(input: StoryCreate, background_tasks: BackgroundTasks, request: Request,
                       user: dict = Depends(get_current_user)):
    if not (GEMINI_API_KEY or EMERGENT_LLM_KEY):
        raise HTTPException(503, "Story generation is not configured yet")
    await accounts.rate_limit(request, 'story-create', limit=15)
    photo_b64 = _strip_data_url(input.photo_base64)
    if photo_b64:
        try:
            from io import BytesIO
            image = Image.open(BytesIO(base64.b64decode(photo_b64, validate=True)))
            if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 40000000:
                raise ValueError('Invalid image')
            image = image.convert('RGB')
            image.thumbnail((1024, 1024))
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            photo_b64 = base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            raise HTTPException(422, 'Please use a valid JPG, PNG, or WebP photo under 10 MB.')
    story_id = str(uuid.uuid4())
    story = {
        "id": story_id,
        "user_id": user["user_id"],
        "ownership": 'parent',
        "generation_photo": photo_b64,
        "child_name": input.child_name,
        "age": input.age,
        "gender": input.gender,
        "theme": input.theme,
        "visual_style": input.visual_style,
        "story_language": input.story_language,
        "story_prompt": input.story_prompt or None,
        "page_count": input.page_count,
        "title": f"{input.child_name}'s Story",
        "pages": [],
        "cover_image": PLACEHOLDER_IMAGE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "narrator_voice": GOOGLE_VOICES[input.voice_id] if GEMINI_API_KEY else input.voice_id,
        "voice_id": input.voice_id,
        "status": "generating",
        "stage": "writing",
        "current_page": 1,
    }
    await db.stories.insert_one({**story})
    background_tasks.add_task(run_story_generation, story_id, input, photo_b64)
    return public_story(story)


@api_router.get("/stories", response_model=List[StoryPublic])
async def get_stories(user: dict = Depends(get_current_user)):
    """Lightweight list: only fetch lightweight fields, skip the heavy pages payload."""
    projection = {
        "_id": 0, "id": 1, "child_name": 1, "age": 1, "gender": 1, "theme": 1,
        "story_language": 1, "title": 1, "cover_image": 1, "created_at": 1,
        "pages.image": 1, "page_count": 1, "status": 1, "voice_id": 1, "narrator_voice": 1,
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
            "page_count": s.get('page_count') or len(pages),
            "status": s.get('status', 'completed'),
            "voice_id": s.get('voice_id', 'nova'),
            "narrator_voice": s.get('narrator_voice', 'nova'),
            "created_at": s.get("created_at"),
        })
    return lite


@api_router.get("/stories/{story_id}", response_model=StoryPublic)
async def get_story(story_id: str, request: Request):
    story, read_only = await authorized_story(story_id, request, allow_share=True)
    return public_story(story, read_only)


@api_router.get('/stories/{story_id}/progress', response_model=StoryProgress)
async def get_story_progress(story_id: str, request: Request):
    story, _ = await authorized_story(story_id, request)
    return progress_of(story)


@api_router.post('/stories/{story_id}/retry', response_model=StoryProgress, status_code=202)
async def retry_story(story_id: str, request: Request, tasks: BackgroundTasks,
                      user: dict = Depends(get_current_user)):
    story, _ = await authorized_story(story_id, request)
    if story.get('user_id') != user['user_id']:
        raise HTTPException(403, 'Save this story to your account before continuing generation.')
    await accounts.rate_limit(request, 'story-retry', limit=10)
    result = await db.stories.update_one({'id': story_id, 'status': {'$in': ['partial', 'failed']}},
                                         {'$set': {'status': 'generating', 'error': None}})
    if not result.modified_count:
        raise HTTPException(409, 'This story is already generating or complete.')
    tasks.add_task(generate_with_progress, story_id, generate_story_text, generate_illustration, generate_narration, AUDIO_DIR)
    return progress_of({**story, 'status': 'generating', 'error': None})


@api_router.post('/stories/{story_id}/claim', response_model=StoryPublic)
async def claim_story(story_id: str, request: Request, user: dict = Depends(get_current_user)):
    story, _ = await authorized_story(story_id, request)
    await claim_guest_stories(request, user['user_id'])
    story, _ = await authorized_story(story_id, request)
    return public_story(story)


@api_router.post('/stories/{story_id}/share')
async def share_story(story_id: str, request: Request, user: dict = Depends(get_current_user)):
    story, _ = await authorized_story(story_id, request)
    if story.get('user_id') != user['user_id']:
        raise HTTPException(403, 'Save this story to your account first.')
    token = secrets.token_urlsafe(32)
    await db.stories.update_one({'id': story_id}, {'$set': {'share_token_hash': digest(token)}})
    return {'url': f'{FRONTEND_URL}/storybook/{story_id}?share={token}'}


@api_router.get('/payments/config')
async def payment_config():
    return {'stripe_enabled': bool(STRIPE_API_KEY), 'midtrans_enabled': bool(MIDTRANS_SERVER_KEY and MIDTRANS_CLIENT_KEY)}


@api_router.post("/orders")
async def create_order(input: OrderCreate, request: Request):
    user = await get_current_user(request)
    story, _ = await authorized_story(input.story_id, request)
    if story.get('user_id') != user['user_id']:
        raise HTTPException(403, 'Save this story to your account before ordering.')
    if story.get('status', 'completed') not in ('complete', 'completed'):
        raise HTTPException(409, 'Finish your story before ordering a printed book.')
    input.origin_url = FRONTEND_URL
    order_id = str(uuid.uuid4())
    is_indonesia = input.country.strip().lower() in ("indonesia", "id")
    gateway = "midtrans" if is_indonesia else "stripe"
    if is_indonesia and not (MIDTRANS_SERVER_KEY and MIDTRANS_CLIENT_KEY):
        raise HTTPException(503, 'Indonesian print checkout is not available yet. Your story is safely saved.')
    if not is_indonesia and not STRIPE_API_KEY:
        raise HTTPException(503, 'Print checkout is not available yet. Your story is safely saved.')

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
        await db.orders.delete_one({'id': order_id})
        raise
    except Exception:
        logging.exception("Payment session creation failed for order %s", order_id)
        await db.orders.delete_one({"id": order_id})
        raise HTTPException(502, "Could not start checkout. Please try again.")

    return {**order, "gateway": gateway, **payment_data}


@api_router.get("/orders", response_model=List[OrderPublic])
async def get_orders(user: dict = Depends(get_current_user)):
    """Return orders for the authenticated user."""
    return await db.orders.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.get("/admin/orders", response_model=List[OrderPublic])
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
async def get_payment_status(order_id: str, user: dict = Depends(get_current_user)):
    order = await db.orders.find_one(
        {"id": order_id, "user_id": user['user_id']},
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
app.include_router(accounts_router)
app.include_router(audio_router)
app.include_router(api_router)

app.add_middleware(SessionMiddleware, secret_key=os.environ['OAUTH_STATE_SECRET'],
                   session_cookie='oauth_state', max_age=600, https_only=True, same_site='lax')


@app.middleware('http')
async def same_origin_writes(request, call_next):
    origin = request.headers.get('origin')
    if request.method in ('POST', 'PATCH', 'PUT', 'DELETE') and origin and origin.rstrip('/') not in TRUSTED_FRONTEND_ORIGINS:
        return JSONResponse({'detail': 'Cross-origin request rejected'}, status_code=403)
    return await call_next(request)

# Serve generated illustrations as static files
app.mount("/api/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
# Serve narration audio as static files
app.mount("/api/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=TRUSTED_FRONTEND_ORIGINS,
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
    from migrate_legacy import migrate
    from pymongo.errors import OperationFailure
    await migrate()
    await db.guest_sessions.create_index('guest_id', unique=True)
    await db.stories.create_index([('user_id', 1), ('created_at', -1)])
    await db.stories.create_index('id', unique=True)
    await db.orders.create_index('user_id')
    await db.user_sessions.create_index('jti', sparse=True)
    await db.auth_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.stories.update_many({'status': {'$in': ['processing', 'generating']}}, {'$set': {
        'status': 'partial', 'error': 'Generation was interrupted. Your completed pages are saved; retry to continue.'}})
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
