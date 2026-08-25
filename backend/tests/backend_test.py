"""Backend regression tests for Kids Storybook API (real Gemini AI generation).

NOTE: POST /api/stories spends real LLM credits (~25-90s each).
This suite intentionally creates only 3 stories total, shared via class-scoped fixtures.
"""
import base64
import os
import struct
import zlib
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing from env and /app/frontend/.env")
BASE_URL = base_url.rstrip("/")

STORY_TIMEOUT = 240


def _make_png(size: int = 64) -> str:
    """Build a tiny valid PNG (solid colour) and return it as a data URL."""
    raw = b""
    for y in range(size):
        raw += b"\x00" + bytes([200, 150, 120] * size)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ---------- Health ----------
class TestHealth:
    def test_root(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["message"] == "Kids Storybook API"
        assert data["ai_enabled"] is True


# ---------- Story generation (real AI) ----------
class TestStories:
    """All story tests share 3 generated stories to limit LLM spend."""

    @pytest.fixture(scope="class")
    def story_en(self, api_client):
        payload = {
            "child_name": "TEST_Riley",
            "age": 6,
            "gender": "Curious",
            "theme": "Ocean Explorer",
            "story_language": "en",
        }
        import time

        start = time.time()
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        elapsed = time.time() - start
        assert r.status_code == 200, f"{r.status_code}: {r.text[:800]}"
        data = r.json()
        data["_elapsed"] = elapsed
        return data

    @pytest.fixture(scope="class")
    def story_id_lang(self, api_client):
        payload = {
            "child_name": "TEST_Bima",
            "age": 5,
            "gender": "Brave",
            "theme": "Jungle Adventure",
            "story_language": "id",
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:800]}"
        return r.json()

    @pytest.fixture(scope="class")
    def story_photo(self, api_client):
        payload = {
            "child_name": "TEST_Maya",
            "age": 7,
            "gender": "Kind",
            "theme": "Space Journey",
            "story_language": "en",
            "photo_base64": _make_png(),
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:800]}"
        return r.json()

    # --- English story structure ---
    def test_english_story_structure(self, story_en):
        assert isinstance(story_en["title"], str) and story_en["title"].strip()
        assert isinstance(story_en["pages"], list)
        assert len(story_en["pages"]) == 32, f"expected 32 pages, got {len(story_en['pages'])}"
        for i, p in enumerate(story_en["pages"]):
            assert p["page"] == i + 1
            assert isinstance(p["text"], str) and len(p["text"].strip()) > 0, f"page {i+1} empty"
            assert isinstance(p["image"], str) and p["image"]
        assert story_en["cover_image"], "cover_image missing"
        assert story_en["child_name"] == "TEST_Riley"
        assert story_en["status"] == "ready"
        assert "id" in story_en

    def test_english_story_images_are_generated_paths(self, story_en):
        imgs = [p["image"] for p in story_en["pages"]]
        for img in imgs:
            assert img.startswith("/api/images/"), f"non-generated image (fallback?): {img}"
        assert len(set(imgs)) == 8, f"expected 8 unique illustrations, got {len(set(imgs))}"
        assert story_en["cover_image"].startswith("/api/images/")

    def test_english_story_is_real_ai_text(self, story_en):
        texts = [p["text"] for p in story_en["pages"]]
        assert len(set(texts)) > 20, "text looks templated/mocked (too many duplicates)"
        joined = " ".join(texts)
        assert "TEST_Riley" in joined or "Riley" in joined
        assert len(joined) > 800, "story text suspiciously short"

    def test_english_story_generation_time(self, story_en):
        assert story_en["_elapsed"] < 90, f"generation took {story_en['_elapsed']:.1f}s (>90s)"

    # --- Indonesian ---
    def test_indonesian_story_language(self, story_id_lang):
        assert len(story_id_lang["pages"]) == 32
        joined = " ".join(p["text"] for p in story_id_lang["pages"]).lower()
        indo_words = ["yang", "dan", "dengan", "tidak", "sangat", "dia", "itu", "ke", "di", "adalah"]
        hits = [w for w in indo_words if f" {w} " in f" {joined} "]
        assert len(hits) >= 3, f"text does not look Indonesian; hits={hits}; sample={joined[:300]}"
        assert story_id_lang["story_language"] == "id"

    # --- With photo reference ---
    def test_story_with_photo(self, story_photo):
        assert len(story_photo["pages"]) == 32
        imgs = {p["image"] for p in story_photo["pages"]}
        assert len(imgs) == 8, f"expected 8 unique illustrations, got {len(imgs)}"
        for img in imgs:
            assert img.startswith("/api/images/"), f"illustration failed / fallback used: {img}"

    # --- Validation ---
    def test_story_validation_error(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/stories", json={"child_name": "TEST_X"}, timeout=30)
        assert r.status_code == 422, r.status_code


# ---------- Read-only story endpoints (no LLM spend) ----------
class TestStoryReads:
    @pytest.fixture(scope="class")
    def story_en(self, api_client):
        """Newest existing story from the list endpoint (avoids extra LLM spend)."""
        r = api_client.get(f"{BASE_URL}/api/stories", timeout=60)
        assert r.status_code == 200, r.text
        items = r.json()
        assert items, "no stories available to read"
        detail = api_client.get(f"{BASE_URL}/api/stories/{items[0]['id']}", timeout=60)
        assert detail.status_code == 200, detail.text
        return detail.json()

    # --- List endpoint ---
    def test_list_stories_lightweight(self, api_client, story_en):
        r = api_client.get(f"{BASE_URL}/api/stories", timeout=60)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and items
        for item in items:
            assert "pages" not in item, "list endpoint must not return pages"
            assert "_id" not in item
            assert "id" in item and "title" in item
            assert "cover_image" in item
            assert "page_count" in item
        mine = next((i for i in items if i["id"] == story_en["id"]), None)
        assert mine is not None, "newly created story missing from list"
        assert mine["page_count"] == 32
        assert mine["title"] == story_en["title"]
        # newest first
        created = [i["created_at"] for i in items if i.get("created_at")]
        assert created == sorted(created, reverse=True), "list not sorted newest first"

    # --- Detail endpoint ---
    def test_get_story_by_id(self, api_client, story_en):
        r = api_client.get(f"{BASE_URL}/api/stories/{story_en['id']}", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" not in data
        assert len(data["pages"]) == 32
        assert data["title"] == story_en["title"]
        assert data["pages"][0]["image"] == story_en["pages"][0]["image"]

    def test_get_story_not_found(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories/does-not-exist-xyz", timeout=30)
        assert r.status_code == 404

    def test_all_illustrations_locally_generated(self, story_en):
        """Every page image should be a generated /api/images/ file, not the Unsplash fallback."""
        fallbacks = [p["image"] for p in story_en["pages"] if not p["image"].startswith("/api/images/")]
        assert not fallbacks, (
            f"{len(fallbacks)}/32 pages use the external placeholder fallback "
            f"(illustration generation failed): {set(fallbacks)}"
        )

    # --- Image serving ---
    def test_image_file_served(self, api_client, story_en):
        paths = [story_en["cover_image"]] + [p["image"] for p in story_en["pages"]]
        generated = [p for p in paths if p.startswith("/api/images/")]
        assert generated, f"no locally generated illustration found (all fallbacks): {set(paths)}"
        path = generated[0]
        r = api_client.get(f"{BASE_URL}{path}", timeout=60)
        assert r.status_code == 200, f"{r.status_code} for {path}"
        assert r.headers.get("content-type", "").startswith("image/png"), r.headers.get("content-type")
        assert len(r.content) > 1000, f"image too small: {len(r.content)} bytes"

    def test_missing_image_returns_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/images/nonexistent-file.png", timeout=30)
        assert r.status_code == 404

    # --- Validation ---
    def test_story_validation_error(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/stories", json={"child_name": "TEST_X"}, timeout=30)
        assert r.status_code == 422, r.status_code


# ---------- Orders (Stripe mocked) ----------
class TestOrders:
    @pytest.fixture(scope="class")
    def order_payload(self):
        return {
            "story_id": "TEST_story_ref",
            "child_name": "TEST_Riley",
            "format": "Softcover",
            "gift_box": True,
            "payment_method": "Stripe",
            "customer_name": "TEST Buyer",
            "email": "test-riley@example.com",
            "address": "1 Test Street",
            "city": "Testville",
            "postal_code": "12345",
        }

    def test_create_order_and_persist(self, api_client, order_payload):
        r = api_client.post(f"{BASE_URL}/api/orders", json=order_payload, timeout=60)
        assert r.status_code == 200, r.text
        order = r.json()
        assert isinstance(order["id"], str) and order["id"]
        assert order["status"] == "Order received"
        assert order["format"] == "Softcover"
        assert order["gift_box"] is True
        assert order["email"] == order_payload["email"]
        assert "_id" not in order

        listing = api_client.get(f"{BASE_URL}/api/orders", timeout=60)
        assert listing.status_code == 200
        found = next((o for o in listing.json() if o["id"] == order["id"]), None)
        assert found is not None, "created order not persisted"
        assert found["status"] == "Order received"

    def test_orders_sorted_newest_first(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/orders", timeout=60)
        assert r.status_code == 200
        orders = r.json()
        for o in orders:
            assert "_id" not in o
        created = [o["created_at"] for o in orders if o.get("created_at")]
        assert created == sorted(created, reverse=True), "orders not sorted newest first"

    def test_update_order_status(self, api_client, order_payload):
        order = api_client.post(f"{BASE_URL}/api/orders", json=order_payload, timeout=60).json()
        r = api_client.patch(
            f"{BASE_URL}/api/orders/{order['id']}", json={"status": "In production"}, timeout=60
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"id": order["id"], "status": "In production"}

        listing = api_client.get(f"{BASE_URL}/api/orders", timeout=60).json()
        found = next(o for o in listing if o["id"] == order["id"])
        assert found["status"] == "In production", "status change not persisted"

    def test_update_order_invalid_status(self, api_client, order_payload):
        order = api_client.post(f"{BASE_URL}/api/orders", json=order_payload, timeout=60).json()
        r = api_client.patch(
            f"{BASE_URL}/api/orders/{order['id']}", json={"status": "Bogus"}, timeout=60
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"

    def test_update_order_not_found(self, api_client):
        r = api_client.patch(
            f"{BASE_URL}/api/orders/no-such-order-id", json={"status": "Shipped"}, timeout=60
        )
        assert r.status_code == 404, r.status_code


# ---------- Cleanup ----------
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    yield
    try:
        import asyncio

        from dotenv import dotenv_values as dv
        from motor.motor_asyncio import AsyncIOMotorClient

        env = dv(str(Path("/app/backend/.env")))
        mongo_url = env.get("MONGO_URL", "").strip('"')
        db_name = env.get("DB_NAME", "").strip('"')
        if not mongo_url or not db_name:
            return

        async def _clean():
            cl = AsyncIOMotorClient(mongo_url)
            db = cl[db_name]
            await db.orders.delete_many({"child_name": {"$regex": "^TEST_"}})
            cl.close()

        asyncio.run(_clean())
    except Exception as exc:  # noqa: BLE001
        print(f"cleanup skipped: {exc}")
