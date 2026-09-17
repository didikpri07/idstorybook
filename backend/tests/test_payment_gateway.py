"""Backend tests for dual payment gateway (Stripe + Midtrans) endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

COMMON_ORDER = {
    "customer_name": "TEST_User",
    "email": "test@example.com",
    "address": "123 Test St",
    "city": "Test City",
    "postal_code": "12345",
    "story_id": "demo",
    "child_name": "TEST_Child",
    "format": "Hardcover",
    "gift_box": False,
    "origin_url": "https://narrative-id.preview.emergentagent.com",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Stripe order ---
class TestStripeOrder:
    """Test Stripe checkout flow for non-Indonesia country."""

    def test_create_order_stripe_status(self, session):
        payload = {**COMMON_ORDER, "country": "United States"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"

    def test_create_order_stripe_gateway_field(self, session):
        payload = {**COMMON_ORDER, "country": "United States"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        data = resp.json()
        assert data.get("gateway") == "stripe", f"Expected gateway=stripe, got {data.get('gateway')}"

    def test_create_order_stripe_checkout_url(self, session):
        payload = {**COMMON_ORDER, "country": "United States"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        data = resp.json()
        url = data.get("checkout_url", "")
        assert url.startswith("https://checkout.stripe.com"), f"Bad checkout_url: {url}"


# --- Midtrans order ---
class TestMidtransOrder:
    """Test Midtrans checkout flow for Indonesia."""

    def test_create_order_midtrans_status(self, session):
        payload = {**COMMON_ORDER, "country": "Indonesia"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"

    def test_create_order_midtrans_gateway_field(self, session):
        payload = {**COMMON_ORDER, "country": "Indonesia"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        data = resp.json()
        assert data.get("gateway") == "midtrans", f"Expected gateway=midtrans, got {data.get('gateway')}"

    def test_create_order_midtrans_snap_token(self, session):
        payload = {**COMMON_ORDER, "country": "Indonesia"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        data = resp.json()
        snap_token = data.get("snap_token", "")
        assert snap_token, f"Missing snap_token: {data}"

    def test_create_order_midtrans_redirect_url(self, session):
        payload = {**COMMON_ORDER, "country": "Indonesia"}
        resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        data = resp.json()
        redirect_url = data.get("redirect_url", "")
        assert redirect_url.startswith("https://app.midtrans.com"), f"Bad redirect_url: {redirect_url}"


# --- Payment status ---
class TestPaymentStatus:
    """Test GET /api/payments/status/{order_id}."""

    def test_payment_status_for_new_order(self, session):
        payload = {**COMMON_ORDER, "country": "United States"}
        order_resp = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
        order_id = order_resp.json().get("id")
        assert order_id, "No order_id in response"

        status_resp = session.get(f"{BASE_URL}/api/payments/status/{order_id}", timeout=10)
        assert status_resp.status_code == 200

        data = status_resp.json()
        assert data.get("payment_status") == "pending"
        assert data.get("payment_gateway") == "stripe"

    def test_payment_status_not_found(self, session):
        resp = session.get(f"{BASE_URL}/api/payments/status/nonexistent-order-id", timeout=10)
        assert resp.status_code == 404


# --- Stripe webhook endpoint ---
class TestStripeWebhook:
    """Verify /api/webhook/stripe exists (GET returns 405, not 404)."""

    def test_stripe_webhook_get_returns_405(self, session):
        resp = session.get(f"{BASE_URL}/api/webhook/stripe", timeout=10)
        assert resp.status_code == 405, f"Expected 405 got {resp.status_code}"


# --- Midtrans notification signature check ---
class TestMidtransNotification:
    """Verify invalid signature returns 403."""

    def test_midtrans_notification_bad_signature(self, session):
        payload = {
            "order_id": "dummy-order",
            "status_code": "200",
            "gross_amount": "549000.00",
            "transaction_status": "settlement",
            "signature_key": "invalidsignature",
        }
        resp = session.post(f"{BASE_URL}/api/payments/midtrans/notification", json=payload, timeout=10)
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"
