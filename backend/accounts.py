"""JWT accounts, backward-compatible sessions, guest ownership, and reset delivery."""
import asyncio
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import httpx
import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from database import db

router = APIRouter(prefix='/api/auth')
SECRET = os.environ['JWT_SECRET']
ORIGIN = os.environ['FRONTEND_URL'].rstrip('/')
SESSION_AGE = 7 * 24 * 3600


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str = ''
    picture: str = ''
    role: str = 'parent'


class AuthResult(BaseModel):
    user: UserPublic
    access_token: str
    token_type: str = 'bearer'


class EmailInput(BaseModel):
    email: EmailStr

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower()


class LoginInput(EmailInput):
    password: str = Field(min_length=1, max_length=128)


class SignupInput(LoginInput):
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def trim_name(cls, value):
        if not value.strip():
            raise ValueError('Name is required')
        return value.strip()

    @field_validator('password')
    @classmethod
    def strong_password(cls, value):
        if len(value) < 8 or len(value.encode()) > 72:
            raise ValueError('Use at least 8 characters and no more than 72 bytes')
        return value


class ResetInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('password')
    @classmethod
    def strong_password(cls, value):
        return SignupInput.strong_password(value)


async def rate_limit(request, action, email='', limit=20):
    # Persistent bounded windows, separate IP and email limits. No plaintext identifiers.
    bucket = int(now().timestamp()) // 900
    ip = (request.headers.get('x-forwarded-for') or request.client.host).split(',')[0].strip()
    for value in [f'ip:{ip}'] + ([f'email:{email}'] if email else []):
        key = digest(f'{action}:{value}:{bucket}')
        entry = await db.auth_limits.find_one_and_update(
            {'_id': key}, {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now() + timedelta(minutes=30)}},
            upsert=True, return_document=ReturnDocument.AFTER, projection={'_id': 0})
        if entry['count'] > limit:
            raise HTTPException(429, 'Too many attempts. Please try again in 15 minutes.')


def guest_id(request):
    token = request.cookies.get('guest_token')
    return digest(token) if token else None


def ensure_guest(request, response):
    token = request.cookies.get('guest_token') or secrets.token_urlsafe(32)
    response.set_cookie('guest_token', token, max_age=365 * 24 * 3600, httponly=True,
                        secure=True, samesite='lax', path='/')
    return digest(token)


async def claim_guest_stories(request, user_id):
    gid = guest_id(request)
    if gid:
        await db.stories.update_many({'guest_id': gid, 'user_id': None},
                                    {'$set': {'user_id': user_id, 'ownership': 'parent'}})
        legacy_free = await db.stories.find_one({'guest_id': gid, 'user_id': user_id, 'page_count': 8,
            'billing': {'$exists': False}, 'status': {'$in': ['complete', 'completed', 'partial']}}, {'_id': 0, 'id': 1})
        if legacy_free:
            await db.users.update_one({'user_id': user_id, 'free_story_id': {'$exists': False}},
                                      {'$set': {'free_story_id': legacy_free['id']}})


async def issue_session(user, response, request):
    jti = secrets.token_urlsafe(32)
    issued = now()
    token = jwt.encode({'sub': user['user_id'], 'jti': jti, 'iat': issued,
                        'exp': issued + timedelta(seconds=SESSION_AGE),
                        'ver': user.get('auth_version', 0)}, SECRET, algorithm='HS256')
    await db.user_sessions.insert_one({'user_id': user['user_id'], 'jti': jti,
                                       'expires_at': issued + timedelta(seconds=SESSION_AGE)})
    response.set_cookie('session_token', token, max_age=SESSION_AGE, httponly=True,
                        secure=True, samesite='lax', path='/')
    await claim_guest_stories(request, user['user_id'])
    return AuthResult(user=UserPublic(**user), access_token=token)


async def get_current_user(request: Request):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.startswith('Bearer ') else request.cookies.get('session_token')
    if not token:
        raise HTTPException(401, 'Not authenticated')
    claims = None
    if token.count('.') == 2:
        try:
            claims = jwt.decode(token, SECRET, algorithms=['HS256'], options={'require': ['sub', 'exp', 'jti', 'iat']})
        except jwt.PyJWTError:
            raise HTTPException(401, 'Session expired or invalid')
        session = await db.user_sessions.find_one({'jti': claims['jti'], 'user_id': claims['sub']}, {'_id': 0})
    else:
        session = await db.user_sessions.find_one({'session_token': token}, {'_id': 0})
    if not session:
        raise HTTPException(401, 'Session expired or invalid')
    expires = session['expires_at']
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.replace(tzinfo=timezone.utc) <= now():
        raise HTTPException(401, 'Session expired')
    user = await db.users.find_one({'user_id': session['user_id']}, {'_id': 0})
    if not user or (claims and claims.get('ver', 0) != user.get('auth_version', 0)):
        raise HTTPException(401, 'Session expired')
    return user


async def get_optional_user(request: Request):
    if not request.cookies.get('session_token') and not request.headers.get('authorization'):
        return None
    return await get_current_user(request)


async def get_admin_user(user=Depends(get_current_user)):
    if user.get('role') != 'admin':
        raise HTTPException(403, 'Admin access required')
    return user


@router.get('/config')
async def auth_config():
    return {'google_enabled': bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET')),
            'password_reset_enabled': bool(os.environ.get('RESEND_API_KEY') and os.environ.get('RESEND_FROM_EMAIL'))}


@router.post('/guest')
async def guest_session(request: Request, response: Response):
    gid = ensure_guest(request, response)
    guest = await db.guest_sessions.find_one({'guest_id': gid}, {'_id': 0, 'story_id': 1})
    return {'story_id': guest.get('story_id') if guest else None}


@router.post('/signup', response_model=AuthResult, status_code=201)
async def signup(body: SignupInput, request: Request, response: Response):
    await rate_limit(request, 'signup', body.email, 10)
    admin_emails = {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}
    if body.email in admin_emails:
        raise HTTPException(409, 'This administrator address is reserved. Use your setup link or sign in.')
    hashed = await asyncio.to_thread(bcrypt.hashpw, body.password.encode(), bcrypt.gensalt())
    user = {'user_id': 'user_' + secrets.token_hex(12), 'email': body.email, 'name': body.name,
            'hashed_password': hashed.decode(), 'role': 'parent', 'created_at': now().isoformat(), 'auth_version': 0}
    try:
        await db.users.insert_one(dict(user))
    except DuplicateKeyError:
        raise HTTPException(409, 'This email is already registered. Please sign in.')
    return await issue_session(user, response, request)


@router.post('/login', response_model=AuthResult)
async def login(body: LoginInput, request: Request, response: Response):
    await rate_limit(request, 'login', body.email)
    user = await db.users.find_one({'email': body.email}, {'_id': 0})
    stored = (user or {}).get('hashed_password')
    # Equal-cost check for nonexistent and Google-only accounts.
    candidate = stored.encode() if stored else b'$2b$12$C6UzMDM.H6dfI/f/IKcEe.5YFXaqGR6KYYSMykkxfEVjxTYIHOWDO'
    valid = await asyncio.to_thread(bcrypt.checkpw, body.password.encode()[:72], candidate)
    if not user or not stored or not valid or len(body.password.encode()) > 72:
        raise HTTPException(401, 'Email or password is incorrect.')
    return await issue_session(user, response, request)


@router.get('/me', response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(**user)


@router.post('/logout')
async def logout(request: Request, response: Response):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.startswith('Bearer ') else request.cookies.get('session_token', '')
    try:
        claims = jwt.decode(token, SECRET, algorithms=['HS256'])
        await db.user_sessions.delete_one({'jti': claims['jti']})
    except (jwt.PyJWTError, KeyError):
        await db.user_sessions.delete_one({'session_token': token})
    response.delete_cookie('session_token', path='/', secure=True, samesite='lax')
    return {'status': 'logged out'}


async def deliver_reset(email, language):
    user = await db.users.find_one({'email': email}, {'_id': 0, 'user_id': 1})
    if not user:
        return
    token = secrets.token_urlsafe(32)
    token_hash = digest(token)
    await db.users.update_one({'user_id': user['user_id']}, {'$set': {
        'password_reset': {'token_hash': token_hash, 'expires_at': now() + timedelta(minutes=30)}}})
    link = f'{ORIGIN}/reset-password?token={token}'
    subject = 'Atur ulang kata sandi IDStorybook' if language == 'id' else 'Reset your IDStorybook password'
    label = 'Atur ulang kata sandi (berlaku 30 menit)' if language == 'id' else 'Reset password (valid for 30 minutes)'
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await client.post('https://api.resend.com/emails',
                headers={'Authorization': f"Bearer {os.environ['RESEND_API_KEY']}"},
                json={'from': os.environ['RESEND_FROM_EMAIL'], 'to': [email], 'subject': subject,
                      'html': f'<p><a href="{link}">{label}</a></p>'})
            result.raise_for_status()
    except Exception:
        import logging
        logging.warning('Password reset email delivery failed; provider response omitted.')
        await db.users.update_one({'user_id': user['user_id'], 'password_reset.token_hash': token_hash},
                                  {'$unset': {'password_reset': ''}})


@router.post('/forgot-password')
async def forgot_password(body: EmailInput, request: Request, tasks: BackgroundTasks):
    await rate_limit(request, 'reset', body.email, 5)
    if not os.environ.get('RESEND_API_KEY') or not os.environ.get('RESEND_FROM_EMAIL'):
        raise HTTPException(503, 'Password reset email is not configured yet.')
    tasks.add_task(deliver_reset, body.email, request.headers.get('x-language', 'en'))
    return {'message': 'If an account exists, a password reset email will be sent.'}


@router.post('/reset-password')
async def reset_password(body: ResetInput, request: Request):
    await rate_limit(request, 'reset-confirm', limit=20)
    hashed = await asyncio.to_thread(bcrypt.hashpw, body.password.encode(), bcrypt.gensalt())
    user = await db.users.find_one_and_update(
        {'password_reset.token_hash': digest(body.token), 'password_reset.expires_at': {'$gt': now()}},
        {'$set': {'hashed_password': hashed.decode()}, '$unset': {'password_reset': ''}, '$inc': {'auth_version': 1}},
        projection={'_id': 0, 'user_id': 1}, return_document=ReturnDocument.AFTER)
    if not user:
        raise HTTPException(400, 'This reset link is invalid or expired.')
    await db.user_sessions.delete_many({'user_id': user['user_id']})
    return {'message': 'Password updated. Please sign in.'}


oauth = OAuth()
if os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET'):
    oauth.register(name='google', client_id=os.environ['GOOGLE_CLIENT_ID'],
                   client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
                   server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                   client_kwargs={'scope': 'openid email profile'})


@router.get('/google')
async def google_start(request: Request):
    if not oauth.create_client('google'):
        raise HTTPException(503, 'Google sign-in is not configured yet.')
    # Only internal return paths; state and nonce are stored/validated by Authlib.
    dest = request.query_params.get('next', '/dashboard')
    request.session['return_to'] = dest if dest.startswith('/') and not dest.startswith('//') and '\\' not in dest else '/dashboard'
    return await oauth.google.authorize_redirect(request, os.environ['GOOGLE_OAUTH_REDIRECT_URI'])


@router.get('/google/callback')
async def google_callback(request: Request):
    if not oauth.create_client('google'):
        raise HTTPException(503, 'Google sign-in is not configured yet.')
    try:
        token = await oauth.google.authorize_access_token(request)
        info = token.get('userinfo')
        if not info or info.get('email_verified') is not True:
            raise ValueError('Verified email required')
        email = info['email'].strip().lower()
        user = await db.users.find_one({'google_id': info['sub']}, {'_id': 0})
        if not user:
            user = await db.users.find_one({'email': email}, {'_id': 0})
        if user and user.get('google_id') not in (None, info['sub']):
            raise ValueError('Identity mismatch')
        if not user:
            admin_emails = {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}
            user = {'user_id': 'user_' + secrets.token_hex(12), 'email': email, 'name': info.get('name', ''),
                    'picture': info.get('picture', ''), 'google_id': info['sub'], 'role': 'admin' if email in admin_emails else 'parent',
                    'created_at': now().isoformat(), 'auth_version': 0}
            await db.users.insert_one(dict(user))
        else:
            await db.users.update_one({'user_id': user['user_id']}, {'$set': {'google_id': info['sub']}})
        destination = request.session.pop('return_to', '/dashboard')
        response = RedirectResponse(ORIGIN + destination, status_code=303)
        await issue_session(user, response, request)
        request.session.clear()
        return response
    except Exception:
        request.session.clear()
        return RedirectResponse(ORIGIN + '/login?error=google', status_code=303)