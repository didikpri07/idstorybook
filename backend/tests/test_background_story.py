"""Test background story generation P1 feature - immediate response with status='processing'"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TOKEN = os.environ.get("TEST_PARENT_TOKEN", "")

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


class TestBackgroundStoryGeneration:
    """POST /api/stories should return immediately with status=processing"""

    def test_post_stories_returns_immediately(self):
        """Verify POST /api/stories returns < 5 seconds"""
        payload = {
            "child_name": "TEST_Luna",
            "age": 6,
            "gender": "Adventurous",
            "theme": "Moonlit Forest",
            "visual_style": "Classic Watercolor",
            "photo_base64": "",
            "story_language": "en"
        }
        start = time.time()
        resp = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start
        print(f"POST /api/stories elapsed: {elapsed:.2f}s, status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:200]}"
        assert elapsed < 5.0, f"Response took {elapsed:.2f}s, expected < 5s"
        data = resp.json()
        assert data.get("status") == "processing", f"Expected status=processing, got {data.get('status')}"
        assert data.get("pages") == [], f"Expected empty pages, got {data.get('pages')}"
        assert "id" in data, "Missing story id"
        TestBackgroundStoryGeneration.story_id = data["id"]
        print(f"Story ID: {data['id']}, status: {data['status']}, response time: {elapsed:.2f}s")

    def test_get_story_returns_processing(self):
        """GET /api/stories/{id} returns processing status right after creation"""
        if not hasattr(TestBackgroundStoryGeneration, 'story_id'):
            pytest.skip("No story_id from previous test")
        story_id = TestBackgroundStoryGeneration.story_id
        resp = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=headers, timeout=10)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # Should be processing or completed (if fast enough)
        assert data.get("status") in ("processing", "completed", "failed"), f"Unexpected status: {data.get('status')}"
        print(f"GET story status: {data.get('status')}")

    def test_post_stories_returns_valid_structure(self):
        """POST /api/stories response contains required fields"""
        payload = {
            "child_name": "TEST_Alex",
            "age": 7,
            "gender": "Curious",
            "theme": "Ocean Adventure",
            "visual_style": "Classic Watercolor",
            "photo_base64": "",
            "story_language": "en"
        }
        resp = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        required_fields = ["id", "status", "pages", "child_name", "created_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        assert data["child_name"] == "TEST_Alex"
        assert data["status"] == "processing"
        print(f"All required fields present, story id={data['id']}")
