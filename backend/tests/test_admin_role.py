"""Admin role-based access control tests for Kids Storybook"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_TOKEN = os.environ.get("TEST_ADMIN_TOKEN", "")
PARENT_TOKEN = os.environ.get("TEST_PARENT_TOKEN_ROLE", "")


def admin_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def parent_headers():
    return {"Authorization": f"Bearer {PARENT_TOKEN}"}


class TestAdminOrders:
    """GET /api/admin/orders access control"""

    def test_admin_orders_with_admin_token_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers())
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: admin/orders with admin token => 200, {len(data)} orders")

    def test_admin_orders_with_parent_token_returns_403(self):
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=parent_headers())
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        data = r.json()
        assert "admin" in data.get("detail", "").lower(), f"Expected 'Admin' in detail: {data}"
        print(f"PASS: admin/orders with parent token => 403")

    def test_admin_orders_without_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/orders")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"PASS: admin/orders without token => 401")


class TestAuthMe:
    """GET /api/auth/me role checking"""

    def test_auth_me_admin_returns_role_admin(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers())
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("role") == "admin", f"Expected role=admin, got: {data.get('role')}"
        assert data.get("email") == "didik.digital@gmail.com", f"Expected admin email, got: {data.get('email')}"
        print(f"PASS: auth/me admin => role=admin, email={data['email']}")

    def test_auth_me_parent_returns_role_parent(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=parent_headers())
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("role") == "parent", f"Expected role=parent, got: {data.get('role')}"
        print(f"PASS: auth/me parent => role=parent")


class TestUpdateOrder:
    """PATCH /api/orders/{id} admin-only"""

    def test_patch_order_with_parent_returns_403(self):
        # Use a dummy order_id first; if no orders exist we still expect 403 not 404
        # First get a real order_id from admin
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers())
        if r.status_code == 200 and r.json():
            order_id = r.json()[0]["id"]
        else:
            order_id = "nonexistent_order_id"
        
        r = requests.patch(f"{BASE_URL}/api/orders/{order_id}", 
                          json={"status": "Shipped"}, 
                          headers=parent_headers())
        assert r.status_code == 403, f"Expected 403 for parent, got {r.status_code}: {r.text}"
        print(f"PASS: PATCH order with parent token => 403")

    def test_patch_order_with_admin_returns_200_or_404(self):
        # Get a real order_id
        r = requests.get(f"{BASE_URL}/api/admin/orders", headers=admin_headers())
        if r.status_code != 200 or not r.json():
            pytest.skip("No orders available to test PATCH")
        
        order_id = r.json()[0]["id"]
        r = requests.patch(f"{BASE_URL}/api/orders/{order_id}", 
                          json={"status": "Shipped"}, 
                          headers=admin_headers())
        assert r.status_code == 200, f"Expected 200 for admin PATCH, got {r.status_code}: {r.text}"
        print(f"PASS: PATCH order with admin token => 200")
