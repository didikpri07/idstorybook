"""
Auth, protected routes, and public endpoints tests for Kids Storybook.
Tests: /api/auth/me, /api/stories, /api/orders, /api/admin/orders, /api/auth/logout
"""
import pytest
import requests
import os
from dotenv import load_dotenv
load_dotenv('/app/frontend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TOKEN = os.environ.get("TEST_PARENT_TOKEN_AUTH", "")


class TestAuthMe:
    def test_auth_me_no_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("PASS: /api/auth/me without token returns 401")

    def test_auth_me_with_token_returns_user(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("name") == "Test Parent", f"Expected 'Test Parent', got {data.get('name')}"
        assert data.get("email") == "testparent@example.com"
        print(f"PASS: /api/auth/me with token returns user: {data.get('name')}")


class TestStoriesProtected:
    def test_get_stories_no_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/stories")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("PASS: GET /api/stories without auth returns 401")

    def test_get_stories_with_auth_returns_list(self):
        r = requests.get(f"{BASE_URL}/api/stories", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/stories with auth returns list of {len(data)} items")


class TestOrdersProtected:
    def test_get_orders_no_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/orders")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("PASS: GET /api/orders without auth returns 401")


class TestAdminOrders:
    def test_get_admin_orders_no_auth_returns_list(self):
        r = requests.get(f"{BASE_URL}/api/admin/orders")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/admin/orders without auth returns {len(data)} orders")


class TestAuthLogout:
    def test_logout_clears_session(self):
        # Logout via Bearer token (cookie-based logout, but we test the endpoint exists and returns OK)
        r = requests.post(f"{BASE_URL}/api/auth/logout", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "logged out"
        print("PASS: POST /api/auth/logout returns {status: logged out}")

    def test_auth_me_after_logout_returns_401(self):
        """After logout the token should be invalid."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 401, f"Expected 401 after logout, got {r.status_code}"
        print("PASS: /api/auth/me after logout returns 401")
