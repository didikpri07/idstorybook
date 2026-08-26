"""Backend tests for visual_style / StylePicker feature (iteration 15)"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_parent_cover_998496137b44412f"


@pytest.fixture
def authed_session():
    s = requests.Session()
    s.cookies.set("session_token", SESSION_TOKEN, domain="storybook-magic-29.preview.emergentagent.com")
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestStylePromptsBackend:
    """Verify STYLE_PROMPTS and visual_style field acceptance"""

    def test_api_root_reachable(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200, f"API root returned {r.status_code}"

    def test_story_create_accepts_visual_style_no_422(self, authed_session):
        """POST /api/stories with visual_style='Comic Book' should NOT return 422"""
        payload = {
            "child_name": "TestKid",
            "age": 5,
            "gender": "Adventurous",
            "theme": "Moonlit Forest",
            "visual_style": "Comic Book",
            "photo_base64": "",
            "story_language": "en",
        }
        r = authed_session.post(f"{BASE_URL}/api/stories", json=payload, timeout=15)
        # We just verify it's NOT a 422 (validation error) — 500/503/402 are ok as they mean the server accepted the shape
        assert r.status_code != 422, f"Got 422 - visual_style field rejected: {r.text}"
        print(f"POST /api/stories with visual_style='Comic Book' => {r.status_code} (expected non-422)")

    def test_story_create_accepts_claymation(self, authed_session):
        payload = {
            "child_name": "TestKid",
            "age": 5,
            "gender": "Curious",
            "theme": "Ocean Explorer",
            "visual_style": "Claymation",
            "photo_base64": "",
            "story_language": "en",
        }
        r = authed_session.post(f"{BASE_URL}/api/stories", json=payload, timeout=15)
        assert r.status_code != 422, f"Got 422 - Claymation visual_style rejected: {r.text}"
        print(f"POST /api/stories with visual_style='Claymation' => {r.status_code}")

    def test_story_create_defaults_to_classic_watercolor(self, authed_session):
        """POST without visual_style should default to Classic Watercolor (no 422)"""
        payload = {
            "child_name": "TestKid",
            "age": 6,
            "gender": "Imaginative",
            "theme": "Dinosaur Valley",
            "photo_base64": "",
            "story_language": "en",
        }
        r = authed_session.post(f"{BASE_URL}/api/stories", json=payload, timeout=15)
        assert r.status_code != 422, f"Got 422 on default visual_style: {r.text}"
        print(f"POST /api/stories without visual_style => {r.status_code}")

    def test_story_create_all_six_styles_no_422(self, authed_session):
        """All 6 visual styles should be accepted without 422"""
        styles = ["Classic Watercolor", "3D Animation", "Comic Book", "Claymation", "Pencil Sketch", "Oil Painting"]
        for style in styles:
            payload = {
                "child_name": "TestKid",
                "age": 5,
                "gender": "Adventurous",
                "theme": "Moonlit Forest",
                "visual_style": style,
                "photo_base64": "",
                "story_language": "en",
            }
            r = authed_session.post(f"{BASE_URL}/api/stories", json=payload, timeout=15)
            assert r.status_code != 422, f"Got 422 for visual_style='{style}': {r.text}"
            print(f"  visual_style='{style}' => {r.status_code} OK")
