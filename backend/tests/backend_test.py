"""Backend regression tests for Kids Storybook API.

NOTE: POST /api/stories spends real LLM credits (~25-90s each) and the Gemini text
budget is currently exhausted. Those generation tests live in TestStoryGeneration and
are skipped unless RUN_LLM_TESTS=1 is exported.

This iteration focuses on:
  * GET /api/stories new lightweight projection
  * GET /api/stories/{id} (seeded narrator-demo-01)
  * static mounts /api/images and /api/audio
  * orders CRUD (Stripe mocked)
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
SEEDED_STORY_ID = "narrator-demo-01"
RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1"
LIST_FIELDS = [
    "id", "title", "cover_image", "page_count", "created_at",
    "child_name", "age", "gender", "theme", "story_language",
]


def _make_png(size: int = 64) -> str:
    """Build a tiny valid PNG (solid colour) and return it as a data URL."""
    raw = b""
    for _y in range(size):
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


# ---------- GET /api/stories (new projection) ----------
class TestStoryList:
    @pytest.fixture(scope="class")
    def items(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and data, "story list empty"
        return data

    def test_list_is_lightweight(self, items):
        for item in items:
            assert "pages" not in item, f"list must not return pages: {item.get('id')}"
            assert "_id" not in item
            assert "illustrations_generated" not in item

    def test_list_item_shape(self, items):
        for item in items:
            for field in LIST_FIELDS:
                assert field in item, f"missing {field} in {item.get('id')}"
            assert isinstance(item["id"], str) and item["id"]
            assert isinstance(item["page_count"], int) and item["page_count"] >= 0
            assert item["story_language"], "story_language should default to en"

    def test_list_sorted_newest_first(self, items):
        created = [i["created_at"] for i in items if i.get("created_at")]
        assert created == sorted(created, reverse=True), "list not sorted newest first"

    def test_cover_image_present_or_falls_back(self, api_client, items):
        """No item should have a null cover when its story actually has page images."""
        broken = []
        for item in items:
            if item["cover_image"] is None and item["page_count"] > 0:
                detail = api_client.get(f"{BASE_URL}/api/stories/{item['id']}", timeout=60).json()
                if any(p.get("image") for p in detail.get("pages", [])):
                    broken.append(item["id"])
        assert not broken, f"cover_image fallback failed for {broken}"

    def test_page_count_matches_detail(self, api_client, items):
        item = items[0]
        detail = api_client.get(f"{BASE_URL}/api/stories/{item['id']}", timeout=60)
        assert detail.status_code == 200, detail.text
        full = detail.json()
        assert item["page_count"] == len(full["pages"])
        assert item["title"] == full["title"]
        assert item["cover_image"] in (full.get("cover_image"), full["pages"][0]["image"])

    def test_seeded_story_in_list(self, items):
        seeded = next((i for i in items if i["id"] == SEEDED_STORY_ID), None)
        assert seeded is not None, f"seeded story {SEEDED_STORY_ID} missing from list"
        assert seeded["cover_image"], "seeded story has no cover image"
        assert seeded["page_count"] > 0


# ---------- GET /api/stories/{id} ----------
class TestStoryDetail:
    def test_seeded_story_detail(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories/{SEEDED_STORY_ID}", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" not in data
        pages = data["pages"]
        assert isinstance(pages, list) and pages
        for i, p in enumerate(pages):
            assert p["page"] == i + 1
            assert isinstance(p["text"], str) and p["text"].strip()
            assert "image" in p
            assert "audio" in p
        assert any(p["audio"] for p in pages), "seeded story has no narration audio"

    def test_story_not_found(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories/does-not-exist-xyz", timeout=30)
        assert r.status_code == 404


# ---------- Static mounts ----------
class TestStaticMounts:
    def test_placeholder_image_served(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/images/placeholder.png", timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("image/png")
        assert len(r.content) > 1000

    def test_missing_image_returns_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/images/nonexistent-file.png", timeout=30)
        assert r.status_code == 404

    def test_narration_audio_served(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/audio/narrator_demo.mp3", timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("audio/mpeg"), \
            r.headers.get("content-type")
        assert len(r.content) > 1000

    def test_missing_audio_returns_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/audio/nope.mp3", timeout=30)
        assert r.status_code == 404

    def test_seeded_story_audio_files_reachable(self, api_client):
        detail = api_client.get(f"{BASE_URL}/api/stories/{SEEDED_STORY_ID}", timeout=60).json()
        audios = {p["audio"] for p in detail["pages"] if p.get("audio")}
        assert audios, "no audio paths on seeded story"
        for path in list(audios)[:3]:
            r = api_client.get(f"{BASE_URL}{path}", timeout=30)
            assert r.status_code == 200, f"{r.status_code} for {path}"


# ---------- Story creation validation (no LLM spend) ----------
class TestStoryCreateValidation:
    def test_story_validation_error(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/stories", json={"child_name": "TEST_X"}, timeout=30)
        assert r.status_code == 422, r.status_code

    def test_story_bad_age_type(self, api_client):
        payload = {
            "child_name": "TEST_X", "age": "notanumber", "gender": "Brave",
            "theme": "Ocean", "story_language": "en",
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=30)
        assert r.status_code == 422, r.status_code


# ---------- Publish-prep checks: data purge + friendly 402 through the ingress ----------
class TestPublishPrep:
    def test_only_seeded_story_remains(self, api_client):
        """QA stories were purged: exactly one story (narrator-demo-01) should remain."""
        r = api_client.get(f"{BASE_URL}/api/stories", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        ids = [s["id"] for s in data]
        assert ids == [SEEDED_STORY_ID], f"expected only {SEEDED_STORY_ID}, got {ids}"

    def test_seeded_story_media_paths(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories/{SEEDED_STORY_ID}", timeout=60)
        assert r.status_code == 200, r.text
        page0 = r.json()["pages"][0]
        assert page0["audio"] == "/api/audio/narrator_demo.mp3", page0["audio"]
        assert isinstance(page0["image"], str) and page0["image"].startswith("/api/images/"), \
            page0["image"]

    def test_budget_exhausted_returns_402_json_through_ingress(self, api_client):
        """The 402 JSON detail must survive the ingress (5xx got swallowed as HTML)."""
        payload = {
            "child_name": "TEST_Ingress", "age": 6, "gender": "Brave",
            "theme": "Ocean Explorer", "story_language": "en",
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 402, f"{r.status_code}: {r.text[:400]}"
        assert r.headers.get("content-type", "").startswith("application/json"), \
            r.headers.get("content-type")
        assert "<html" not in r.text.lower(), "JSON body replaced by an HTML error page"
        body = r.json()
        assert body["detail"] == (
            "AI credit budget exceeded. Please top up your Emergent LLM key balance."
        ), body

    def test_402_for_other_languages(self, api_client):
        payload = {
            "child_name": "TEST_Ingress2", "age": 4, "gender": "Kind",
            "theme": "Space Journey", "story_language": "hi",
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 402, f"{r.status_code}: {r.text[:400]}"
        assert "budget" in r.json()["detail"].lower()

    def test_no_story_persisted_on_failure(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stories", timeout=60)
        assert [s["id"] for s in r.json()] == [SEEDED_STORY_ID], \
            "failed generation leaked a story into the DB"


# ---------- Story generation (real AI, skipped by default) ----------
@pytest.mark.skipif(not RUN_LLM, reason="LLM budget exhausted; export RUN_LLM_TESTS=1 to run")
class TestStoryGeneration:
    def test_generate_story(self, api_client):
        payload = {
            "child_name": "TEST_Riley", "age": 6, "gender": "Curious",
            "theme": "Ocean Explorer", "story_language": "en",
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:800]}"
        data = r.json()
        assert len(data["pages"]) == 32
        assert data["cover_image"]

    def test_generate_story_with_photo(self, api_client):
        payload = {
            "child_name": "TEST_Maya", "age": 7, "gender": "Kind",
            "theme": "Space Journey", "story_language": "en",
            "photo_base64": _make_png(),
        }
        r = api_client.post(f"{BASE_URL}/api/stories", json=payload, timeout=STORY_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:800]}"
        assert len(r.json()["pages"]) == 32


# ---------- Orders (Stripe mocked) ----------
class TestOrders:
    def test_orders_clean_before_publish(self, api_client):
        """Publish prep expects no leftover QA orders in Mongo."""
        r = api_client.get(f"{BASE_URL}/api/orders", timeout=60)
        assert r.status_code == 200, r.text
        leftovers = [
            o for o in r.json()
            if not str(o.get("child_name", "")).startswith("TEST_")
        ]
        assert leftovers == [], (
            "leftover non-TEST orders present: "
            f"{[(o['id'], o.get('child_name')) for o in leftovers]}"
        )

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
        assert order["created_at"]
        assert "_id" not in order

        listing = api_client.get(f"{BASE_URL}/api/orders", timeout=60)
        assert listing.status_code == 200
        found = next((o for o in listing.json() if o["id"] == order["id"]), None)
        assert found is not None, "created order not persisted"
        assert found["status"] == "Order received"
        assert found["customer_name"] == order_payload["customer_name"]

    def test_create_order_missing_fields(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/orders", json={"child_name": "TEST_X"}, timeout=30)
        assert r.status_code == 422, r.status_code

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


# ---------- Cleanup (never touches the seeded narrator-demo-01 story) ----------
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
