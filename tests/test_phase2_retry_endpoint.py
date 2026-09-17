"""Phase 2 retry endpoint tests: conflicts, ownership, single-launch race, and progress transitions."""

import asyncio
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


# Module: in-process app auth helpers and isolated DB fixtures
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
def cleanup_retry_fixture_data(mongo):
    yield
    users = list(mongo.users.find({'email': {'$regex': '^retryphase2_'}}, {'_id': 0, 'user_id': 1}))
    user_ids = [u['user_id'] for u in users if u.get('user_id')]
    if user_ids:
        mongo.user_sessions.delete_many({'user_id': {'$in': user_ids}})
        mongo.users.delete_many({'user_id': {'$in': user_ids}})
    mongo.stories.delete_many({'id': {'$regex': '^TEST_RETRY_'}})


def _create_user_and_token(mongo, label: str):
    user_id = f'user_retry_{uuid.uuid4().hex[:12]}'
    email = f'retryphase2_{label}_{uuid.uuid4().hex[:8]}@example.com'
    now = datetime.now(timezone.utc)
    mongo.users.insert_one({
        'user_id': user_id,
        'email': email,
        'name': f'TEST Retry {label}',
        'role': 'parent',
        'created_at': now.isoformat(),
        'auth_version': 0,
    })
    jti = secrets.token_urlsafe(16)
    mongo.user_sessions.insert_one({'user_id': user_id, 'jti': jti, 'expires_at': now + timedelta(hours=1)})
    token = jwt.encode(
        {'sub': user_id, 'jti': jti, 'iat': now, 'exp': now + timedelta(hours=1), 'ver': 0},
        JWT_SECRET,
        algorithm='HS256',
    )
    return user_id, token


def _insert_story(mongo, *, story_id: str, user_id: str, status: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    pages = [{'page': 1, 'text': 'Page one', 'image': '/api/images/placeholder.png', 'audio': '/api/audio/fake.mp3', 'sentence_timestamps': [], 'complete': True}]
    mongo.stories.insert_one({
        'id': story_id,
        'user_id': user_id,
        'ownership': 'parent',
        'child_name': 'TEST Kid',
        'title': 'TEST Retry Story',
        'age': 6,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'page_count': 2,
        'voice_id': 'nova',
        'narrator_voice': 'Sulafat',
        'pages': pages if status in {'partial', 'complete', 'completed'} else [],
        'cover': {'title': 'TEST Retry Story', 'image': '/api/images/placeholder.png'},
        'cover_image': '/api/images/placeholder.png',
        'status': status,
        'stage': 'narrating' if status == 'partial' else 'complete',
        'current_page': 1,
        'created_at': now_iso,
    })


def test_retry_returns_409_for_generating_or_complete_and_denies_other_parent(mongo, event_loop_runner):
    owner_id, owner_token = _create_user_and_token(mongo, 'owner')
    _other_id, other_token = _create_user_and_token(mongo, 'other')

    generating_id = f'TEST_RETRY_GENERATING_{uuid.uuid4().hex[:8]}'
    complete_id = f'TEST_RETRY_COMPLETE_{uuid.uuid4().hex[:8]}'
    partial_id = f'TEST_RETRY_PARTIAL_{uuid.uuid4().hex[:8]}'
    _insert_story(mongo, story_id=generating_id, user_id=owner_id, status='generating')
    _insert_story(mongo, story_id=complete_id, user_id=owner_id, status='complete')
    _insert_story(mongo, story_id=partial_id, user_id=owner_id, status='partial')

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            owner_headers = {'Authorization': f'Bearer {owner_token}'}
            other_headers = {'Authorization': f'Bearer {other_token}'}
            generating_retry = await client.post(f'/api/stories/{generating_id}/retry', headers=owner_headers)
            complete_retry = await client.post(f'/api/stories/{complete_id}/retry', headers=owner_headers)
            other_parent_retry = await client.post(f'/api/stories/{partial_id}/retry', headers=other_headers)
            return generating_retry.status_code, complete_retry.status_code, other_parent_retry.status_code

    generating_code, complete_code, other_code = event_loop_runner.run_until_complete(_run())
    assert generating_code == 409
    assert complete_code == 409
    assert other_code == 404


def test_competing_retries_only_launch_background_once(mongo, monkeypatch, event_loop_runner):
    owner_id, owner_token = _create_user_and_token(mongo, 'race')
    story_id = f'TEST_RETRY_RACE_{uuid.uuid4().hex[:8]}'
    _insert_story(mongo, story_id=story_id, user_id=owner_id, status='partial')

    launches = []

    async def fake_generate(*args, **kwargs):
        launches.append(args[0])
        await asyncio.sleep(0.05)

    monkeypatch.setattr(server_module, 'generate_with_progress', fake_generate)

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            headers = {'Authorization': f'Bearer {owner_token}'}
            r1, r2 = await asyncio.gather(
                client.post(f'/api/stories/{story_id}/retry', headers=headers),
                client.post(f'/api/stories/{story_id}/retry', headers=headers),
            )
            return sorted([r1.status_code, r2.status_code])

    statuses = event_loop_runner.run_until_complete(_run())
    assert statuses == [202, 409]
    assert launches == [story_id]


def test_progress_stage_page_percent_change_after_retry_checkpoints(mongo, monkeypatch, event_loop_runner):
    owner_id, owner_token = _create_user_and_token(mongo, 'progress')
    story_id = f'TEST_RETRY_PROGRESS_{uuid.uuid4().hex[:8]}'
    _insert_story(mongo, story_id=story_id, user_id=owner_id, status='partial')

    async def fake_generate(story_id_arg, *_args, **_kwargs):
        await server_module.db.stories.update_one(
            {'id': story_id_arg},
            {'$set': {'status': 'generating', 'stage': 'illustrating', 'current_page': 2, 'error': None}},
        )
        await asyncio.sleep(0.08)
        await server_module.db.stories.update_one(
            {'id': story_id_arg},
            {'$set': {
                'status': 'generating',
                'stage': 'narrating',
                'current_page': 2,
                'pages': [
                    {'page': 1, 'text': 'Page one', 'image': '/api/images/placeholder.png', 'audio': '/api/audio/fake.mp3', 'sentence_timestamps': [], 'complete': True},
                    {'page': 2, 'text': 'Page two', 'image': '/api/images/placeholder.png', 'audio': '/api/audio/fake.mp3', 'sentence_timestamps': [], 'complete': True},
                ],
                'completed_pages': 2,
            }},
        )
        await asyncio.sleep(0.08)
        await server_module.db.stories.update_one(
            {'id': story_id_arg},
            {'$set': {'status': 'complete', 'stage': 'complete', 'current_page': 2, 'completed_pages': 2}},
        )

    monkeypatch.setattr(server_module, 'generate_with_progress', fake_generate)

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            headers = {'Authorization': f'Bearer {owner_token}'}
            first_progress = await client.get(f'/api/stories/{story_id}/progress', headers=headers)
            retry = await client.post(f'/api/stories/{story_id}/retry', headers=headers)
            snapshots = [first_progress.json(), retry.json()]
            for _ in range(12):
                await asyncio.sleep(0.05)
                progress = await client.get(f'/api/stories/{story_id}/progress', headers=headers)
                snapshots.append(progress.json())
                if progress.json()['status'] == 'complete':
                    break
            return first_progress.status_code, retry.status_code, snapshots

    first_code, retry_code, snapshots = event_loop_runner.run_until_complete(_run())
    assert first_code == 200
    assert retry_code == 202

    statuses = {s['status'] for s in snapshots}
    stages = {s['stage'] for s in snapshots}
    percents = {s['percent'] for s in snapshots}
    pages = {s['current_page'] for s in snapshots}

    assert 'generating' in statuses
    assert snapshots[-1]['status'] == 'complete'
    assert snapshots[-1]['percent'] == 100
    assert len(stages) >= 2
    assert len(percents) >= 2
    assert len(pages) >= 2