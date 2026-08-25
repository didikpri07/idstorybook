import os
import requests
from pathlib import Path

if not os.environ.get("REACT_APP_BACKEND_URL"):
    for line in (Path(__file__).parents[2] / "frontend" / ".env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def test_health_and_story_flow():
    health = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert health.status_code == 200
    assert health.json()["demo_mode"] is True

    payload = {"child_name": "TEST_Riley", "age": 6, "gender": "Curious", "theme": "Ocean Explorer", "photo_url": ""}
    created = requests.post(f"{BASE_URL}/api/stories", json=payload, timeout=30)
    assert created.status_code == 200
    story = created.json()
    assert story["child_name"] == payload["child_name"]
    assert len(story["pages"]) == 3
    stories = requests.get(f"{BASE_URL}/api/stories", timeout=15)
    assert stories.status_code == 200
    assert any(item["id"] == story["id"] for item in stories.json())


def test_order_and_status_flow():
    payload = {"story_id": "TEST_story", "child_name": "TEST_Riley", "format": "Softcover", "gift_box": False,
               "payment_method": "Stripe", "customer_name": "TEST Buyer", "email": "test-riley@example.com",
               "address": "1 Test Street", "city": "Testville", "postal_code": "12345"}
    created = requests.post(f"{BASE_URL}/api/orders", json=payload, timeout=30)
    assert created.status_code == 200
    order = created.json()
    assert order["format"] == "Softcover"
    orders = requests.get(f"{BASE_URL}/api/orders", timeout=15)
    assert orders.status_code == 200
    assert any(item["id"] == order["id"] for item in orders.json())
    updated = requests.patch(f"{BASE_URL}/api/orders/{order['id']}", json={"status": "Shipped"}, timeout=15)
    assert updated.status_code == 200
    assert updated.json() == {"id": order["id"], "status": "Shipped"}
