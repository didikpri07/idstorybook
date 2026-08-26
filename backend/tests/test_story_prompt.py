"""Tests for story_prompt (optional) feature on POST /api/stories"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
AUTH_TOKEN = "test_session_fresh_2a000bb7046b4c57"

HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}

STORY_BASE = {
    "child_name": "TEST_Aria",
    "age": 7,
    "gender": "Adventurous",
    "theme": "Moonlit Forest",
    "visual_style": "Classic Watercolor",
    "story_language": "en",
}


class TestStoryPromptAPI:
    """Tests for story_prompt field in POST /api/stories"""

    def test_create_story_without_prompt_returns_processing(self):
        """Backward compat: no story_prompt => status=processing, story_prompt=None"""
        payload = {**STORY_BASE}
        r = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=HEADERS, timeout=20)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "processing", f"Expected processing, got {data.get('status')}"
        assert data.get("story_prompt") is None, f"Expected None, got {data.get('story_prompt')}"
        print(f"PASS: story without prompt created, id={data.get('id')}, story_prompt={data.get('story_prompt')}")

    def test_create_story_with_prompt_returns_processing(self):
        """With story_prompt: status=processing and prompt stored correctly"""
        prompt_text = "My 7-year-old doesn't want to sleep over at grandma's. Help them feel brave."
        payload = {**STORY_BASE, "story_prompt": prompt_text}
        r = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=HEADERS, timeout=20)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "processing", f"Expected processing, got {data.get('status')}"
        assert data.get("story_prompt") == prompt_text, f"Prompt mismatch: {data.get('story_prompt')}"
        print(f"PASS: story with prompt created, id={data.get('id')}, story_prompt='{data.get('story_prompt')}'")

    def test_create_story_prompt_persisted_via_get(self):
        """Verify story_prompt is persisted in DB via GET /api/stories/{id}"""
        prompt_text = "My child is scared of the dark. Help them find courage."
        payload = {**STORY_BASE, "story_prompt": prompt_text}
        r = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=HEADERS, timeout=20)
        assert r.status_code == 200
        story_id = r.json().get("id")
        assert story_id

        # GET to verify persistence
        gr = requests.get(f"{BASE_URL}/api/stories/{story_id}", timeout=10)
        assert gr.status_code == 200, f"GET failed: {gr.status_code}"
        gdata = gr.json()
        assert gdata.get("story_prompt") == prompt_text, f"Prompt not persisted: {gdata.get('story_prompt')}"
        print(f"PASS: story_prompt persisted in DB for id={story_id}")

    def test_create_story_with_empty_string_prompt(self):
        """Empty string story_prompt is treated as null-like"""
        payload = {**STORY_BASE, "story_prompt": ""}
        r = requests.post(f"{BASE_URL}/api/stories", json=payload, headers=HEADERS, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "processing"
        # Backend does `input.story_prompt or None` so empty string -> None
        assert data.get("story_prompt") is None, f"Expected None for empty prompt, got '{data.get('story_prompt')}'"
        print(f"PASS: empty story_prompt stored as None")

    def test_create_story_without_auth_still_works(self):
        """story creation works without auth (guest user)"""
        payload = {**STORY_BASE, "story_prompt": "Test prompt without auth"}
        r = requests.post(f"{BASE_URL}/api/stories", json=payload, timeout=20)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "processing"
        assert data.get("story_prompt") == "Test prompt without auth"
        print(f"PASS: story with prompt works without auth, id={data.get('id')}")
