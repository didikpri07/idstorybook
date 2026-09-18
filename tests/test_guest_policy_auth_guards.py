"""Guest-mode policy guards for create/retry auth, ownership, and trusted user_id assignment."""

import asyncio
import hashlib
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient


if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from server import app  # noqa: E402
import server as server_module  # noqa: E402


# Module: env and db fixtures
BACKEND_ENV = dotenv_values('/app/backend/.env')
MONGO_URL = os.environ.get('MONGO_URL') or BACKEND_ENV.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME') or BACKEND_ENV.get('DB_NAME')
JWT_SECRET = os.environ.get('JWT_SECRET') or BACKEND_ENV.get('JWT_SECRET')


@pytest.fixture(scope='session')
def assert_env_ready():
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


@pytest.fixture(autouse=True)
def policy_fixture_state(mongo):
    state = {
        'user_ids': set(),
        'story_ids': set(),
        'child_names': set(),
    }
    yield state
    # Delete stories first using captured IDs/owners to avoid orphaned fixture rows.
    story_filters = []
    if state['story_ids']:
        story_filters.append({'id': {'$in': list(state['story_ids'])}})
    if state['user_ids']:
        story_filters.append({'user_id': {'$in': list(state['user_ids'])}})
    if state['child_names']:
        story_filters.append({'child_name': {'$in': list(state['child_names'])}})
    if story_filters:
        mongo.stories.delete_many({'$or': story_filters})
    # Safety cleanup for legacy test IDs only.
    mongo.stories.delete_many({'id': {'$regex': '^TEST_AUTHPOL_'}})
    if state['user_ids']:
        mongo.user_sessions.delete_many({'user_id': {'$in': list(state['user_ids'])}})
        mongo.users.delete_many({'user_id': {'$in': list(state['user_ids'])}})
    mongo.guest_sessions.delete_many({'story_id': {'$regex': '^TEST_AUTHPOL_'}})


def _insert_user_session(mongo, state: dict, label: str, expires_delta: timedelta = timedelta(hours=1)):
    user_id = f'user_authpol_{uuid.uuid4().hex[:12]}'
    email = f'authpol_{label}_{uuid.uuid4().hex[:8]}@example.com'
    now_dt = datetime.now(timezone.utc)
    mongo.users.insert_one({
        'user_id': user_id,
        'email': email,
        'name': f'TEST Auth Policy {label}',
        'role': 'parent',
        'created_at': now_dt.isoformat(),
        'auth_version': 0,
    })
    jti = secrets.token_urlsafe(16)
    exp = now_dt + expires_delta
    mongo.user_sessions.insert_one({'user_id': user_id, 'jti': jti, 'expires_at': exp})
    token = jwt.encode({'sub': user_id, 'jti': jti, 'iat': now_dt, 'exp': exp, 'ver': 0}, JWT_SECRET, algorithm='HS256')
    state['user_ids'].add(user_id)
    return user_id, token


def _story_payload(**overrides):
    payload = {
        'child_name': 'TEST Policy Kid',
        'age': 6,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'story_prompt': 'A brave bedtime adventure.',
        'page_count': 8,
        'voice_id': 'nova',
        'photo_base64': None,
    }
    payload.update(overrides)
    return payload


# Module: create story auth guards
def test_anonymous_and_invalid_or_expired_jwt_cannot_create_story_or_launch_tasks(mongo, monkeypatch, event_loop_runner, policy_fixture_state):
    task_launches = []

    async def fake_run_story_generation(*args, **kwargs):
        task_launches.append(args[0])
        await asyncio.sleep(0)

    monkeypatch.setattr(server_module, 'run_story_generation', fake_run_story_generation)
    _, expired_token = _insert_user_session(mongo, policy_fixture_state, 'expired', expires_delta=timedelta(minutes=-1))
    anon_child = f'TEST_AUTHPOL_ANON_{uuid.uuid4().hex[:8]}'
    badjwt_child = f'TEST_AUTHPOL_BADJWT_{uuid.uuid4().hex[:8]}'
    expired_child = f'TEST_AUTHPOL_EXPIRED_{uuid.uuid4().hex[:8]}'
    policy_fixture_state['child_names'].update([anon_child, badjwt_child, expired_child])
    before = mongo.stories.count_documents({'child_name': {'$in': [anon_child, badjwt_child, expired_child]}})

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            anonymous = await client.post('/api/stories', json=_story_payload(child_name=anon_child))
            invalid = await client.post('/api/stories', json=_story_payload(child_name=badjwt_child), headers={'Authorization': 'Bearer definitely.invalid.token'})
            expired = await client.post('/api/stories', json=_story_payload(child_name=expired_child), headers={'Authorization': f'Bearer {expired_token}'})
            return anonymous.status_code, invalid.status_code, expired.status_code

    anon_code, invalid_code, expired_code = event_loop_runner.run_until_complete(_run())
    after = mongo.stories.count_documents({'child_name': {'$in': [anon_child, badjwt_child, expired_child]}})

    assert anon_code == 401
    assert invalid_code == 401
    assert expired_code == 401
    assert before == after
    assert task_launches == []


def test_authenticated_create_202_uses_authenticated_owner_and_ignores_client_user_id(mongo, monkeypatch, event_loop_runner, policy_fixture_state):
    launches = []

    async def fake_run_story_generation(story_id, *_args, **_kwargs):
        launches.append(story_id)
        await asyncio.sleep(0)

    monkeypatch.setattr(server_module, 'run_story_generation', fake_run_story_generation)

    owner_id, owner_token = _insert_user_session(mongo, policy_fixture_state, 'owner')
    child_name = f'TEST_AUTHPOL_CREATE_OK_{uuid.uuid4().hex[:8]}'
    policy_fixture_state['child_names'].add(child_name)
    payload = _story_payload(child_name=child_name, user_id='user_spoofed_by_client')

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            return await client.post('/api/stories', json=payload, headers={'Authorization': f'Bearer {owner_token}'})

    res = event_loop_runner.run_until_complete(_run())
    assert res.status_code == 202
    body = res.json()
    policy_fixture_state['story_ids'].add(body['id'])
    assert body['child_name'] == payload['child_name']
    assert body['status'] == 'generating'

    stored = mongo.stories.find_one({'id': body['id']}, {'_id': 0, 'user_id': 1, 'child_name': 1, 'ownership': 1})
    assert stored['user_id'] == owner_id
    assert stored['ownership'] == 'parent'
    assert stored['child_name'] == payload['child_name']
    assert launches == [body['id']]


# Module: retry auth and ownership guards
def test_anonymous_retry_401_even_with_matching_guest_cookie_and_owner_retry_202(mongo, monkeypatch, event_loop_runner, policy_fixture_state):
    launches = []

    async def fake_generate_with_progress(*args, **kwargs):
        launches.append(args[0])
        await asyncio.sleep(0)

    monkeypatch.setattr(server_module, 'generate_with_progress', fake_generate_with_progress)

    owner_id, owner_token = _insert_user_session(mongo, policy_fixture_state, 'retryowner')
    other_id, other_token = _insert_user_session(mongo, policy_fixture_state, 'retryother')

    story_id = f'TEST_AUTHPOL_RETRY_{uuid.uuid4().hex[:10]}'
    policy_fixture_state['story_ids'].add(story_id)
    guest_raw = secrets.token_urlsafe(16)
    guest_hash = hashlib.sha256(guest_raw.encode()).hexdigest()
    mongo.stories.insert_one({
        'id': story_id,
        'user_id': owner_id,
        'ownership': 'parent',
        'guest_id': guest_hash,
        'child_name': 'Retry Kid',
        'age': 6,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'page_count': 8,
        'voice_id': 'nova',
        'narrator_voice': 'Sulafat',
        'title': 'Retry Story',
        'pages': [{'page': 1, 'text': 'One page done', 'image': '/api/images/placeholder.png', 'audio': '/api/audio/fake.mp3', 'sentence_timestamps': [], 'complete': True}],
        'status': 'partial',
        'stage': 'narrating',
        'current_page': 2,
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            anon_ip = f"198.51.100.{secrets.randbelow(200) + 1}"
            other_ip = f"203.0.113.{secrets.randbelow(200) + 1}"
            owner_ip = f"192.0.2.{secrets.randbelow(200) + 1}"
            anonymous_retry = await client.post(
                f'/api/stories/{story_id}/retry',
                headers={'Cookie': f'guest_token={guest_raw}', 'X-Forwarded-For': anon_ip},
            )
            other_parent_retry = await client.post(
                f'/api/stories/{story_id}/retry',
                headers={'Authorization': f'Bearer {other_token}', 'X-Forwarded-For': other_ip},
            )
            owner_retry = await client.post(
                f'/api/stories/{story_id}/retry',
                headers={'Authorization': f'Bearer {owner_token}', 'X-Forwarded-For': owner_ip},
            )
            return anonymous_retry.status_code, other_parent_retry.status_code, owner_retry.status_code

    anon_code, other_code, owner_code = event_loop_runner.run_until_complete(_run())

    assert anon_code == 401
    assert other_code == 404
    assert owner_code == 202
    assert launches == [story_id]
