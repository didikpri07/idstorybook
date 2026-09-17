"""Phase 2 API regression tests for auth, ownership, guest claim, progress, voice, and timings."""

import asyncio
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Module: environment and shared clients
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


@pytest.fixture(scope='session')
def mongo(assert_env_ready):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        yield db
    finally:
        client.close()


def _new_session():
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        # Isolate per-run limits without deleting shared auth_limits documents.
        'X-Forwarded-For': f"198.18.{secrets.randbelow(255)}.{secrets.randbelow(255)}",
    })
    return session


@pytest.fixture(autouse=True)
def cleanup_test_data(mongo):
    """Cleanup only TEST_* and test-prefix records created by this module."""
    yield

    test_prefixes = [
        'testphase2_', 'resetknown_', 'authflow_', 'privacy_', 'role_',
        'ownera_', 'ownerb_', 'guestclaim_', 'resetflow_', 'progressisolation_'
    ]
    email_regex = '^(' + '|'.join(test_prefixes) + ')' 
    users = list(mongo.users.find(
        {
            '$or': [
                {'email': {'$regex': email_regex, '$options': 'i'}},
                {'name': {'$regex': '^TEST_P2_'}},
            ]
        },
        {'_id': 0, 'user_id': 1}
    ))
    user_ids = [u['user_id'] for u in users if u.get('user_id')]

    if user_ids:
        mongo.user_sessions.delete_many({'user_id': {'$in': user_ids}})
        mongo.users.delete_many({'user_id': {'$in': user_ids}})

    mongo.stories.delete_many({'id': {'$regex': '^TEST_'}})
    mongo.orders.delete_many({'id': {'$regex': '^TEST_'}})
    mongo.guest_sessions.delete_many({'story_id': {'$regex': '^TEST_'}})


@pytest.fixture
def api_client(assert_env_ready):
    return _new_session()


def _signup_and_get_user(client: requests.Session, email: str, password: str, name: str):
    res = client.post(f'{BASE_URL}/api/auth/signup', json={'email': email, 'password': password, 'name': name})
    assert res.status_code == 201, res.text
    data = res.json()
    assert data['user']['email'] == email.strip().lower()
    assert isinstance(data['access_token'], str) and data['access_token']
    return data


def _new_identity(prefix='testphase2'):
    token = uuid.uuid4().hex[:8]
    return f'{prefix}_{token}@example.com', f'TEST_P2_{token}', f'Pwd-{token}-1234'


# Module: auth and session behavior
def test_auth_config_google_and_reset_disabled(api_client):
    cfg = api_client.get(f'{BASE_URL}/api/auth/config')
    assert cfg.status_code == 200
    data = cfg.json()
    assert data['google_enabled'] is False
    assert data['password_reset_enabled'] is False

    g = api_client.get(f'{BASE_URL}/api/auth/google', allow_redirects=False)
    assert g.status_code == 503
    assert 'not configured' in g.json().get('detail', '').lower()


def test_forgot_password_disabled_for_known_and_unknown_email(api_client):
    known_email, known_name, known_password = _new_identity('resetknown')
    _signup_and_get_user(api_client, known_email, known_password, known_name)

    known = api_client.post(f'{BASE_URL}/api/auth/forgot-password', json={'email': known_email})
    unknown = api_client.post(f'{BASE_URL}/api/auth/forgot-password', json={'email': f'unknown_{uuid.uuid4().hex[:6]}@example.com'})

    assert known.status_code == 503
    assert unknown.status_code == 503
    assert 'not configured yet' in known.json().get('detail', '').lower()


def test_signup_login_duplicate_wrong_password_jwt_and_logout(api_client):
    email_raw, name, password = _new_identity('authflow')
    mixed_case = email_raw.upper()

    created = api_client.post(f'{BASE_URL}/api/auth/signup', json={'email': mixed_case, 'name': name, 'password': password})
    assert created.status_code == 201
    create_data = created.json()
    assert create_data['user']['email'] == email_raw
    assert create_data['user']['role'] == 'parent'

    dup = api_client.post(f'{BASE_URL}/api/auth/signup', json={'email': email_raw, 'name': name, 'password': password})
    assert dup.status_code == 409

    logout = api_client.post(f'{BASE_URL}/api/auth/logout')
    assert logout.status_code == 200

    after_logout = api_client.get(f'{BASE_URL}/api/auth/me')
    assert after_logout.status_code == 401

    bad_login = api_client.post(f'{BASE_URL}/api/auth/login', json={'email': email_raw, 'password': 'wrong-password'})
    assert bad_login.status_code == 401

    good_login = api_client.post(f'{BASE_URL}/api/auth/login', json={'email': email_raw, 'password': password})
    assert good_login.status_code == 200
    token = good_login.json()['access_token']
    if JWT_SECRET:
        claims = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        assert claims['sub'] == good_login.json()['user']['user_id']
        assert claims['exp'] > claims['iat']
        assert 'jti' in claims and isinstance(claims['jti'], str)


def test_auth_me_never_leaks_sensitive_fields(api_client):
    email, name, password = _new_identity('privacy')
    _signup_and_get_user(api_client, email, password, name)
    me = api_client.get(f'{BASE_URL}/api/auth/me')
    assert me.status_code == 200
    body = me.json()
    assert 'hashed_password' not in body
    assert 'password_reset' not in body


def test_parent_cannot_escalate_to_admin(api_client):
    email, name, password = _new_identity('role')
    _signup_and_get_user(api_client, email, password, name)
    admin_orders = api_client.get(f'{BASE_URL}/api/admin/orders')
    assert admin_orders.status_code == 403


# Module: private ownership, share access, and payment status isolation
def test_private_ownership_and_share_read_only(mongo, api_client):
    a_email, a_name, a_password = _new_identity('ownera')
    b_email, b_name, b_password = _new_identity('ownerb')

    a = _new_session()
    b = _new_session()

    a_user = _signup_and_get_user(a, a_email, a_password, a_name)['user']
    b_user = _signup_and_get_user(b, b_email, b_password, b_name)['user']

    story_a_id = f'TEST_story_{uuid.uuid4().hex[:10]}'
    story_b_id = f'TEST_story_{uuid.uuid4().hex[:10]}'
    now_iso = datetime.now(timezone.utc).isoformat()
    base_story = {
        'child_name': 'TEST Child', 'title': 'TEST Title', 'age': 6, 'gender': 'Curious', 'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor', 'story_language': 'en', 'page_count': 8,
        'pages': [{'page': 1, 'text': 'Once upon a time.', 'image': '/api/images/placeholder.png', 'audio': '/api/audio/fake.mp3', 'sentence_timestamps': [], 'complete': True}],
        'cover': {'title': 'TEST Title', 'image': '/api/images/placeholder.png'},
        'cover_image': '/api/images/placeholder.png', 'status': 'complete', 'voice_id': 'nova', 'narrator_voice': 'Sulafat',
        'current_page': 8, 'stage': 'complete', 'created_at': now_iso,
    }

    mongo.stories.insert_many([
        {**base_story, 'id': story_a_id, 'user_id': a_user['user_id'], 'ownership': 'parent'},
        {**base_story, 'id': story_b_id, 'user_id': b_user['user_id'], 'ownership': 'parent'},
    ])

    order_a_id = f'TEST_order_{uuid.uuid4().hex[:8]}'
    order_b_id = f'TEST_order_{uuid.uuid4().hex[:8]}'
    base_order = {
        'child_name': 'TEST Child', 'format': 'Hardcover', 'customer_name': 'Parent', 'email': 'x@example.com',
        'address': 'Test Street', 'city': 'Jakarta', 'postal_code': '12345', 'country': 'Indonesia',
        'status': 'Order received', 'payment_status': 'pending', 'created_at': now_iso,
    }
    mongo.orders.insert_many([
        {**base_order, 'id': order_a_id, 'story_id': story_a_id, 'user_id': a_user['user_id'], 'payment_gateway': 'midtrans'},
        {**base_order, 'id': order_b_id, 'story_id': story_b_id, 'user_id': b_user['user_id'], 'payment_gateway': 'stripe'},
    ])

    a_list = a.get(f'{BASE_URL}/api/stories')
    assert a_list.status_code == 200
    a_ids = {s['id'] for s in a_list.json()}
    assert story_a_id in a_ids
    assert story_b_id not in a_ids

    forbidden_story = a.get(f'{BASE_URL}/api/stories/{story_b_id}')
    assert forbidden_story.status_code == 404

    own_progress = a.get(f'{BASE_URL}/api/stories/{story_a_id}/progress')
    assert own_progress.status_code == 200
    assert own_progress.json()['status'] in {'complete', 'completed'}

    other_progress = b.get(f'{BASE_URL}/api/stories/{story_a_id}/progress')
    assert other_progress.status_code == 404

    own_payment = a.get(f'{BASE_URL}/api/payments/status/{order_a_id}')
    assert own_payment.status_code == 200
    assert own_payment.json()['id'] == order_a_id

    other_payment = b.get(f'{BASE_URL}/api/payments/status/{order_a_id}')
    assert other_payment.status_code == 404

    share = a.post(f'{BASE_URL}/api/stories/{story_a_id}/share')
    assert share.status_code == 200
    share_url = share.json()['url']
    assert 'share=' in share_url
    share_token = share_url.split('share=')[1]

    anon = requests.Session()
    open_shared = anon.get(f'{BASE_URL}/api/stories/{story_a_id}', params={'share': share_token})
    assert open_shared.status_code == 200
    assert open_shared.json()['read_only'] is True

    blocked_direct = anon.get(f'{BASE_URL}/api/stories/{story_a_id}')
    assert blocked_direct.status_code == 404


# Module: guest cookie claim and single-story enforcement
def test_guest_claim_and_no_second_guest_story(mongo):
    guest = _new_session()

    first_guest = guest.post(f'{BASE_URL}/api/auth/guest')
    assert first_guest.status_code == 200
    assert first_guest.json().get('story_id') is None

    guest_token = guest.cookies.get('guest_token')
    assert isinstance(guest_token, str) and guest_token
    gid = hashlib.sha256(guest_token.encode()).hexdigest()

    existing_story_id = f'TEST_guest_{uuid.uuid4().hex[:10]}'
    now_iso = datetime.now(timezone.utc).isoformat()
    mongo.stories.insert_one({
        'id': existing_story_id,
        'user_id': None,
        'guest_id': gid,
        'ownership': 'guest',
        'child_name': 'Guest Kid',
        'title': 'Guest Story',
        'age': 5,
        'gender': 'Curious',
        'theme': 'Ocean Explorer',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'page_count': 8,
        'pages': [],
        'cover_image': '/api/images/placeholder.png',
        'status': 'generating',
        'stage': 'writing',
        'current_page': 1,
        'voice_id': 'nova',
        'narrator_voice': 'Sulafat',
        'created_at': now_iso,
    })
    mongo.guest_sessions.update_one(
        {'guest_id': gid},
        {'$set': {'guest_id': gid, 'story_id': existing_story_id, 'created_at': datetime.now(timezone.utc)}},
        upsert=True,
    )

    second_guest = guest.post(f'{BASE_URL}/api/auth/guest')
    assert second_guest.status_code == 200
    assert second_guest.json().get('story_id') == existing_story_id

    denied_second_creation = guest.post(
        f'{BASE_URL}/api/stories',
        json={
            'child_name': 'Guest Kid', 'age': 5, 'gender': 'Curious', 'theme': 'Moonlit Forest',
            'visual_style': 'Classic Watercolor', 'story_language': 'en', 'page_count': 8, 'voice_id': 'nova'
        },
    )
    assert denied_second_creation.status_code == 403

    new_email, new_name, new_password = _new_identity('guestclaim')
    claimed = guest.post(
        f'{BASE_URL}/api/auth/signup',
        json={'email': new_email, 'name': new_name, 'password': new_password},
    )
    assert claimed.status_code == 201
    user_id = claimed.json()['user']['user_id']

    after_claim = guest.get(f'{BASE_URL}/api/stories/{existing_story_id}')
    assert after_claim.status_code == 200
    assert after_claim.json()['is_guest'] is False

    db_story = mongo.stories.find_one({'id': existing_story_id}, {'_id': 0, 'user_id': 1, 'guest_id': 1})
    assert db_story['user_id'] == user_id
    assert db_story['guest_id'] == gid


# Module: reset token one-time usage, expiry, and session invalidation
def test_reset_token_one_time_expiry_and_session_invalidation(mongo):
    client = _new_session()
    email, name, old_password = _new_identity('resetflow')
    created = _signup_and_get_user(client, email, old_password, name)
    user_id = created['user']['user_id']

    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    mongo.users.update_one(
        {'user_id': user_id},
        {'$set': {'password_reset': {'token_hash': token_hash, 'expires_at': datetime.now(timezone.utc) + timedelta(minutes=5)}}},
    )

    new_password = 'Reset-NewPass-1234'
    reset_ok = client.post(f'{BASE_URL}/api/auth/reset-password', json={'token': token, 'password': new_password})
    assert reset_ok.status_code == 200

    same_cookie_me = client.get(f'{BASE_URL}/api/auth/me')
    assert same_cookie_me.status_code == 401

    reuse = client.post(f'{BASE_URL}/api/auth/reset-password', json={'token': token, 'password': 'Another-Pass-1234'})
    assert reuse.status_code == 400

    expired_token = secrets.token_urlsafe(24)
    mongo.users.update_one(
        {'user_id': user_id},
        {'$set': {'password_reset': {'token_hash': hashlib.sha256(expired_token.encode()).hexdigest(), 'expires_at': datetime.now(timezone.utc) - timedelta(minutes=1)}}},
    )
    expired = client.post(f'{BASE_URL}/api/auth/reset-password', json={'token': expired_token, 'password': 'Expired-NotUsed-1234'})
    assert expired.status_code == 400

    relogin = client.post(f'{BASE_URL}/api/auth/login', json={'email': email, 'password': new_password})
    assert relogin.status_code == 200
    assert relogin.json()['user']['user_id'] == user_id


# Module: progress schema and completed story timing integrity
def test_progress_endpoint_and_voice_on_real_completed_story():
    qa = _new_session()
    login = qa.post(f'{BASE_URL}/api/auth/login', json={'email': QA_EMAIL, 'password': QA_PASSWORD})
    assert login.status_code == 200

    progress = qa.get(f'{BASE_URL}/api/stories/{QA_STORY_ID}/progress')
    assert progress.status_code == 200
    payload = progress.json()
    assert payload['status'] in {'complete', 'completed'}
    assert isinstance(payload['current_page'], int)
    assert isinstance(payload['total_pages'], int)
    assert payload['total_pages'] == 8
    assert payload['percent'] == 100
    assert payload['estimated_seconds_remaining'] == 0

    story = qa.get(f'{BASE_URL}/api/stories/{QA_STORY_ID}')
    assert story.status_code == 200
    data = story.json()
    assert '_id' not in data
    assert 'generation_draft' not in data
    assert 'generation_photo' not in data
    assert 'guest_id' not in data
    assert 'share_token_hash' not in data
    assert data['voice_id'] == 'onyx'
    assert data['narrator_voice'] == 'Algenib'

    pages = data['pages']
    assert len(pages) == 8
    for p in pages:
        assert isinstance(p.get('audio'), str) and p['audio']
        assert isinstance(p.get('duration_ms'), int) and p['duration_ms'] > 0
        timings = p.get('sentence_timestamps') or []
        assert timings, f"Missing timings on page {p.get('page')}"
        last_end = 0
        for t in timings:
            assert t['start_ms'] >= last_end
            assert t['end_ms'] >= t['start_ms']
            last_end = t['end_ms']
        assert abs(last_end - p['duration_ms']) <= 200


def test_progress_private_for_another_parent(api_client):
    email, name, password = _new_identity('progressisolation')
    _signup_and_get_user(api_client, email, password, name)
    not_owner = api_client.get(f'{BASE_URL}/api/stories/{QA_STORY_ID}/progress')
    assert not_owner.status_code == 404


# Module: voice validation guardrails
def test_invalid_voice_rejected_with_validation_error(api_client):
    invalid = api_client.post(
        f'{BASE_URL}/api/stories',
        json={
            'child_name': 'Voice Test',
            'age': 6,
            'gender': 'Curious',
            'theme': 'Moonlit Forest',
            'visual_style': 'Classic Watercolor',
            'story_language': 'en',
            'page_count': 8,
            'voice_id': 'invalid_voice',
        },
    )
    assert invalid.status_code == 422


# Module: migration idempotency and ownership tagging
def test_migration_tags_missing_user_id_records_idempotently(mongo, event_loop_runner):
    s_id = f'TEST_migration_story_{uuid.uuid4().hex[:8]}'
    o_id = f'TEST_migration_order_{uuid.uuid4().hex[:8]}'
    now_iso = datetime.now(timezone.utc).isoformat()
    mongo.stories.insert_one({'id': s_id, 'title': 'Legacy story', 'created_at': now_iso})
    mongo.orders.insert_one({'id': o_id, 'status': 'Order received', 'created_at': now_iso})

    import sys
    if '/app/backend' not in sys.path:
        sys.path.append('/app/backend')
    from migrate_legacy import migrate

    # First migration run (actual migration function)
    first = event_loop_runner.run_until_complete(migrate())
    assert first['stories_tagged'] >= 1
    assert first['orders_tagged'] >= 1

    # Idempotency check (second run should not modify the same inserted docs)
    second = event_loop_runner.run_until_complete(migrate())
    assert second['stories_tagged'] == 0
    assert second['orders_tagged'] == 0

    story = mongo.stories.find_one({'id': s_id}, {'_id': 0, 'user_id': 1, 'ownership': 1})
    order = mongo.orders.find_one({'id': o_id}, {'_id': 0, 'user_id': 1, 'ownership': 1})
    assert story == {'user_id': None, 'ownership': 'legacy/guest'}
    assert order == {'user_id': None, 'ownership': 'legacy/guest'}


# Module: route integrity checks
def test_auth_me_and_logout_routes_are_not_duplicated():
    import sys
    if '/app/backend' not in sys.path:
        sys.path.append('/app/backend')
    from server import app

    counts = {}
    for route in app.routes:
        path = getattr(route, 'path', None)
        methods = getattr(route, 'methods', set()) or set()
        if path in {'/api/auth/me', '/api/auth/logout'}:
            for method in methods:
                key = (method, path)
                counts[key] = counts.get(key, 0) + 1

    assert counts.get(('GET', '/api/auth/me'), 0) == 1
    assert counts.get(('POST', '/api/auth/logout'), 0) == 1