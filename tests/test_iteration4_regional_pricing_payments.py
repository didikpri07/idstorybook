"""Iteration 4 regression: regional pricing, admin pricing guards, payment gating, free-book reservation."""

import asyncio
import copy
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient


if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from server import app  # noqa: E402
import server as server_module  # noqa: E402


# Module: shared environment, session, and cleanup fixtures
FRONTEND_ENV = dotenv_values('/app/frontend/.env')
BACKEND_ENV = dotenv_values('/app/backend/.env')

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or FRONTEND_ENV.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL') or BACKEND_ENV.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME') or BACKEND_ENV.get('DB_NAME')
JWT_SECRET = os.environ.get('JWT_SECRET') or BACKEND_ENV.get('JWT_SECRET')

QA_EMAIL = 'phase2.qa@example.com'
QA_PASSWORD = 'Storybook-QA-2026!'
QA_STORY_ID = 'e62b417b-03b1-4278-99a7-3e4c5d00d386'


@pytest.fixture(scope='session')
def assert_env_ready():
    assert BASE_URL, 'REACT_APP_BACKEND_URL is required'
    assert MONGO_URL, 'MONGO_URL is required'
    assert DB_NAME, 'DB_NAME is required'
    assert JWT_SECRET, 'JWT_SECRET is required'


@pytest.fixture(scope='session')
def mongo(assert_env_ready):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        yield db
    finally:
        client.close()


@pytest.fixture
def tracker():
    state = {'story_ids': set(), 'order_ids': set(), 'user_ids': set()}
    yield state


@pytest.fixture(autouse=True)
def cleanup_iteration4_fixtures(mongo, tracker):
    yield
    if tracker['story_ids']:
        mongo.stories.delete_many({'id': {'$in': list(tracker['story_ids'])}})
    # Also clean by child_name prefix for deterministic safety.
    mongo.stories.delete_many({'child_name': {'$regex': '^TEST_IT4_'}})
    if tracker['order_ids']:
        mongo.orders.delete_many({'id': {'$in': list(tracker['order_ids'])}})
    if tracker['story_ids']:
        mongo.orders.delete_many({'story_id': {'$in': list(tracker['story_ids'])}})
    if tracker['user_ids']:
        mongo.user_sessions.delete_many({'user_id': {'$in': list(tracker['user_ids'])}})
        mongo.users.delete_many({'user_id': {'$in': list(tracker['user_ids'])}})


def _session():
    s = requests.Session()
    s.headers.update({
        'Content-Type': 'application/json',
        'X-Forwarded-For': f"198.18.{secrets.randbelow(255)}.{secrets.randbelow(255)}",
    })
    return s


def _login(email=QA_EMAIL, password=QA_PASSWORD):
    s = _session()
    r = s.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    return s, r.json()


def _make_admin_session(mongo, tracker):
    user_id = f'user_it4_admin_{uuid.uuid4().hex[:12]}'
    email = f'it4_admin_{uuid.uuid4().hex[:8]}@example.com'
    now_dt = datetime.now(timezone.utc)
    mongo.users.insert_one({
        'user_id': user_id,
        'email': email,
        'name': 'TEST IT4 Admin',
        'role': 'admin',
        'created_at': now_dt.isoformat(),
        'auth_version': 0,
    })
    jti = secrets.token_urlsafe(16)
    exp = now_dt + timedelta(hours=2)
    mongo.user_sessions.insert_one({'user_id': user_id, 'jti': jti, 'expires_at': exp})
    token = jwt.encode({'sub': user_id, 'jti': jti, 'iat': now_dt, 'exp': exp, 'ver': 0}, JWT_SECRET, algorithm='HS256')

    tracker['user_ids'].add(user_id)
    s = _session()
    s.headers['Authorization'] = f'Bearer {token}'
    return s


def _new_parent_user(mongo, tracker, label='it4parent'):
    user_id = f'user_{label}_{uuid.uuid4().hex[:10]}'
    email = f'{label}_{uuid.uuid4().hex[:8]}@example.com'
    now_dt = datetime.now(timezone.utc)
    mongo.users.insert_one({
        'user_id': user_id,
        'email': email,
        'name': f'TEST IT4 {label}',
        'role': 'parent',
        'created_at': now_dt.isoformat(),
        'auth_version': 0,
    })
    jti = secrets.token_urlsafe(16)
    exp = now_dt + timedelta(hours=1)
    mongo.user_sessions.insert_one({'user_id': user_id, 'jti': jti, 'expires_at': exp})
    token = jwt.encode({'sub': user_id, 'jti': jti, 'iat': now_dt, 'exp': exp, 'ver': 0}, JWT_SECRET, algorithm='HS256')
    tracker['user_ids'].add(user_id)
    return user_id, token


# Module: public pricing and role enforcement
def test_public_pricing_exact_24_entries_and_policy_fields(assert_env_ready):
    response = _session().get(f'{BASE_URL}/api/pricing')
    assert response.status_code == 200
    data = response.json()

    assert data['free_pages'] == 8
    assert data['free_books_per_account'] == 1
    assert data['pdf_free'] is True

    id_rows = data['regions']['ID']['prices']
    other_rows = data['regions']['OTHER']['prices']
    assert len(id_rows) == 4
    assert len(other_rows) == 4
    assert sum(len([r['digital'], r['softcover'], r['hardcover']]) for r in id_rows + other_rows) == 24

    expected_id = {
        8: (15000, 100000, 150000),
        16: (25000, 200000, 250000),
        24: (39000, 340000, 390000),
        32: (49000, 440000, 490000),
    }
    expected_other = {
        8: (100, 1000, 1500),
        16: (195, 1800, 2500),
        24: (295, 2500, 3900),
        32: (395, 3200, 4900),
    }
    for row in id_rows:
        assert (row['digital'], row['softcover'], row['hardcover']) == expected_id[row['pages']]
        assert isinstance(row['digital'], int)
    for row in other_rows:
        assert (row['digital'], row['softcover'], row['hardcover']) == expected_other[row['pages']]
        assert isinstance(row['digital'], int)

    # Ensure stale legacy values are not present.
    all_digital = {r['digital'] for r in id_rows + other_rows}
    assert 2200 not in all_digital
    assert 3400 not in all_digital


def test_parent_cannot_update_admin_pricing(assert_env_ready):
    parent, _ = _login()
    catalog = parent.get(f'{BASE_URL}/api/pricing').json()
    denied = parent.put(f'{BASE_URL}/api/admin/pricing', json=catalog)
    assert denied.status_code == 403


# Module: admin pricing save/persist/conflict and restoration
def test_admin_pricing_update_conflict_and_restore(mongo, tracker):
    admin = _make_admin_session(mongo, tracker)

    baseline = admin.get(f'{BASE_URL}/api/pricing')
    assert baseline.status_code == 200
    original = baseline.json()
    modified = copy.deepcopy(original)

    # mutate one price, then restore entire baseline in this same test
    original_row = next(r for r in original['regions']['OTHER']['prices'] if r['pages'] == 16)
    assert original_row['digital'] == 195
    for row in modified['regions']['OTHER']['prices']:
        if row['pages'] == 16:
            row['digital'] = row['digital'] + 1
            break

    saved = admin.put(f'{BASE_URL}/api/admin/pricing', json=modified)
    assert saved.status_code == 200, saved.text
    after_save = saved.json()
    saved_row = next(r for r in after_save['regions']['OTHER']['prices'] if r['pages'] == 16)
    assert saved_row['digital'] == original_row['digital'] + 1

    stale_conflict = admin.put(f'{BASE_URL}/api/admin/pricing', json=modified)
    assert stale_conflict.status_code == 409

    # restore all values (version may increment, values must revert)
    restore_payload = {
        **original,
        'version': after_save['version'],
        'updated_at': after_save.get('updated_at', ''),
    }
    restored = admin.put(f'{BASE_URL}/api/admin/pricing', json=restore_payload)
    assert restored.status_code == 200, restored.text
    restored_data = restored.json()
    restored_row = next(r for r in restored_data['regions']['OTHER']['prices'] if r['pages'] == 16)
    assert restored_row['digital'] == original_row['digital']


# Module: digital payment-gate behavior and idempotency
def test_paid_story_creation_is_awaiting_payment_and_blocks_retry_and_share(tracker):
    qa, _ = _login()
    pricing = qa.get(f'{BASE_URL}/api/pricing').json()
    version = pricing['version']
    paid_amount = next(r for r in pricing['regions']['OTHER']['prices'] if r['pages'] == 16)['digital']

    request_id = str(uuid.uuid4())
    create_payload = {
        'child_name': f'TEST_IT4_PAID_{uuid.uuid4().hex[:8]}',
        'age': 7,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'story_prompt': 'A short brave adventure.',
        'page_count': 16,
        'voice_id': 'nova',
        'photo_base64': None,
        'region': 'OTHER',
        'expected_amount': paid_amount,
        'pricing_version': version,
        'request_id': request_id,
    }

    created = qa.post(f'{BASE_URL}/api/stories', json=create_payload)
    assert created.status_code == 202, created.text
    story = created.json()
    tracker['story_ids'].add(story['id'])
    tracker['order_ids'].add(story['billing']['order_id'])
    assert story['status'] == 'awaiting_payment'
    assert story['billing']['kind'] == 'paid'
    assert story['billing']['authorized'] is False
    assert story['billing']['amount_minor'] == paid_amount
    assert story['pages'] == []

    retry = qa.post(f"{BASE_URL}/api/stories/{story['id']}/retry")
    assert retry.status_code == 402

    share = qa.post(f"{BASE_URL}/api/stories/{story['id']}/share")
    assert share.status_code == 409


def test_malicious_paid_amount_override_is_rejected_409():
    qa, _ = _login()
    pricing = qa.get(f'{BASE_URL}/api/pricing').json()
    payload = {
        'child_name': f'TEST_IT4_BADAMOUNT_{uuid.uuid4().hex[:8]}',
        'age': 7,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'story_prompt': 'Amount tamper check.',
        'page_count': 16,
        'voice_id': 'nova',
        'photo_base64': None,
        'region': 'OTHER',
        'expected_amount': 0,
        'pricing_version': pricing['version'],
        'request_id': str(uuid.uuid4()),
    }
    denied = qa.post(f'{BASE_URL}/api/stories', json=payload)
    assert denied.status_code == 409


def test_story_create_idempotent_same_request_id_same_story_and_order(tracker):
    qa, data = _login()
    user_id = data['user']['user_id']
    pricing = qa.get(f'{BASE_URL}/api/pricing').json()
    paid_amount = next(r for r in pricing['regions']['OTHER']['prices'] if r['pages'] == 16)['digital']
    req = str(uuid.uuid4())

    payload = {
        'child_name': f'TEST_IT4_IDEMPOTENT_{uuid.uuid4().hex[:8]}',
        'age': 8,
        'gender': 'Adventurous',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'story_prompt': 'Idempotency check.',
        'page_count': 16,
        'voice_id': 'nova',
        'photo_base64': None,
        'region': 'OTHER',
        'expected_amount': paid_amount,
        'pricing_version': pricing['version'],
        'request_id': req,
    }

    first = qa.post(f'{BASE_URL}/api/stories', json=payload)
    second = qa.post(f'{BASE_URL}/api/stories', json=payload)
    assert first.status_code == 202
    assert second.status_code == 202
    a, b = first.json(), second.json()
    tracker['story_ids'].add(a['id'])
    tracker['order_ids'].add(a['billing']['order_id'])
    assert a['id'] == b['id']
    assert a['billing']['order_id'] == b['billing']['order_id']

    expected_story_id = str(uuid.uuid5(uuid.NAMESPACE_URL, user_id + req))
    assert a['id'] == expected_story_id


# Module: print pricing uses owned story page_count and owner-only order access
def test_print_order_uses_story_page_count_snapshot_and_owner_only_read(mongo, tracker):
    qa, _ = _login()
    pricing = qa.get(f'{BASE_URL}/api/pricing').json()
    version = pricing['version']

    create = qa.post(f'{BASE_URL}/api/orders', json={
        'story_id': QA_STORY_ID,
        'format': 'Hardcover',
        'customer_name': 'QA Parent',
        'email': QA_EMAIL,
        'address': 'Jl Test 123',
        'city': 'Jakarta',
        'postal_code': '12345',
        'country': 'Other',
        'expected_amount': 1500,
        'pricing_version': version,
        'request_id': str(uuid.uuid4()),
    })
    assert create.status_code == 201, create.text
    order = create.json()
    tracker['order_ids'].add(order['id'])
    assert order['kind'] == 'print'
    assert order['page_count'] == 8
    assert order['amount_minor'] == 1500
    assert order['currency'] == 'USD'
    assert order['payment_gateway'] == 'stripe'
    assert order['price_snapshot']['page_count'] == 8

    owner_view = qa.get(f"{BASE_URL}/api/orders/{order['id']}")
    assert owner_view.status_code == 200

    other_session = _session()
    other_email = f'test_it4_other_{uuid.uuid4().hex[:8]}@example.com'
    other_password = 'Storybook-QA-2026!'
    signup = other_session.post(f'{BASE_URL}/api/auth/signup', json={'email': other_email, 'password': other_password, 'name': 'TEST IT4 Other'})
    assert signup.status_code == 201
    tracker['user_ids'].add(signup.json()['user']['user_id'])
    forbidden = other_session.get(f"{BASE_URL}/api/orders/{order['id']}")
    assert forbidden.status_code == 404


# Module: isolated free allowance reservation and paid second 8-page behavior
def test_concurrent_free_requests_only_one_reserves_and_second_409(mongo, tracker, monkeypatch, event_loop_runner):
    launches = []

    async def fake_run_story_generation(story_id, *_args, **_kwargs):
        launches.append(story_id)
        await asyncio.sleep(0)

    monkeypatch.setattr(server_module, 'run_story_generation', fake_run_story_generation)
    _, token = _new_parent_user(mongo, tracker, 'it4free')

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            body = {
                'age': 7,
                'gender': 'Curious',
                'theme': 'Moonlit Forest',
                'visual_style': 'Classic Watercolor',
                'story_language': 'en',
                'voice_id': 'nova',
                'photo_base64': None,
                'region': 'OTHER',
                'page_count': 8,
                'expected_amount': 0,
                'pricing_version': 1,
            }
            c1 = dict(body, child_name=f'TEST_IT4_FREE_A_{uuid.uuid4().hex[:6]}', request_id=str(uuid.uuid4()))
            c2 = dict(body, child_name=f'TEST_IT4_FREE_B_{uuid.uuid4().hex[:6]}', request_id=str(uuid.uuid4()))
            headers = {'Authorization': f'Bearer {token}', 'X-Forwarded-For': f"203.0.113.{secrets.randbelow(200) + 1}"}
            return await asyncio.gather(
                client.post('/api/stories', json=c1, headers=headers),
                client.post('/api/stories', json=c2, headers=headers),
            )

    res1, res2 = event_loop_runner.run_until_complete(_run())
    codes = sorted([res1.status_code, res2.status_code])
    assert codes == [202, 409]
    assert len(launches) == 1


def test_after_free_consumed_second_8_page_requires_paid_quote(mongo, tracker, monkeypatch, event_loop_runner):
    async def fake_run_story_generation(*_args, **_kwargs):
        await asyncio.sleep(0)

    monkeypatch.setattr(server_module, 'run_story_generation', fake_run_story_generation)
    _, token = _new_parent_user(mongo, tracker, 'it4freepaid')

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            headers = {'Authorization': f'Bearer {token}', 'X-Forwarded-For': f"198.51.100.{secrets.randbelow(200) + 1}"}
            pricing = (await client.get('/api/pricing')).json()
            version = pricing['version']
            paid_8 = next(r for r in pricing['regions']['OTHER']['prices'] if r['pages'] == 8)['digital']
            first = await client.post('/api/stories', json={
                'child_name': f'TEST_IT4_FIRSTFREE_{uuid.uuid4().hex[:6]}',
                'age': 6,
                'gender': 'Curious',
                'theme': 'Moonlit Forest',
                'visual_style': 'Classic Watercolor',
                'story_language': 'en',
                'voice_id': 'nova',
                'photo_base64': None,
                'region': 'OTHER',
                'page_count': 8,
                'expected_amount': 0,
                'pricing_version': version,
                'request_id': str(uuid.uuid4()),
            }, headers=headers)
            second_bad = await client.post('/api/stories', json={
                'child_name': f'TEST_IT4_SECONDFREE_{uuid.uuid4().hex[:6]}',
                'age': 6,
                'gender': 'Curious',
                'theme': 'Moonlit Forest',
                'visual_style': 'Classic Watercolor',
                'story_language': 'en',
                'voice_id': 'nova',
                'photo_base64': None,
                'region': 'OTHER',
                'page_count': 8,
                'expected_amount': 0,
                'pricing_version': version,
                'request_id': str(uuid.uuid4()),
            }, headers=headers)
            second_paid = await client.post('/api/stories', json={
                'child_name': f'TEST_IT4_SECONDPAID_{uuid.uuid4().hex[:6]}',
                'age': 6,
                'gender': 'Curious',
                'theme': 'Moonlit Forest',
                'visual_style': 'Classic Watercolor',
                'story_language': 'en',
                'voice_id': 'nova',
                'photo_base64': None,
                'region': 'OTHER',
                'page_count': 8,
                'expected_amount': paid_8,
                'pricing_version': version,
                'request_id': str(uuid.uuid4()),
            }, headers=headers)
            return first, second_bad, second_paid

    first, second_bad, second_paid = event_loop_runner.run_until_complete(_run())
    assert first.status_code == 202
    assert first.json()['billing']['kind'] == 'free'
    assert second_bad.status_code == 409
    assert second_paid.status_code == 202
    assert second_paid.json()['status'] == 'awaiting_payment'
    assert second_paid.json()['billing']['kind'] == 'paid'
