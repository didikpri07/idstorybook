"""Restore exact regional pricing defaults for test cleanup."""

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


frontend_env = dotenv_values('/app/frontend/.env')
backend_env = dotenv_values('/app/backend/.env')

base_url = (os.environ.get('REACT_APP_BACKEND_URL') or frontend_env.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
mongo_url = os.environ.get('MONGO_URL') or backend_env.get('MONGO_URL')
db_name = os.environ.get('DB_NAME') or backend_env.get('DB_NAME')
jwt_secret = os.environ.get('JWT_SECRET') or backend_env.get('JWT_SECRET')

assert base_url and mongo_url and db_name and jwt_secret

client = MongoClient(mongo_url)
db = client[db_name]

user_id = f'user_restore_{secrets.token_hex(6)}'
email = f'restore_{secrets.token_hex(4)}@example.com'
now_dt = datetime.now(timezone.utc)
db.users.insert_one({'user_id': user_id, 'email': email, 'name': 'Restore Admin', 'role': 'admin', 'created_at': now_dt.isoformat(), 'auth_version': 0})
jti = secrets.token_urlsafe(16)
exp = now_dt + timedelta(hours=1)
db.user_sessions.insert_one({'user_id': user_id, 'jti': jti, 'expires_at': exp})
token = jwt.encode({'sub': user_id, 'jti': jti, 'iat': now_dt, 'exp': exp, 'ver': 0}, jwt_secret, algorithm='HS256')

session = requests.Session()
session.headers.update({'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'X-Forwarded-For': f"198.18.{secrets.randbelow(255)}.{secrets.randbelow(255)}"})

pricing = session.get(f'{base_url}/api/pricing', timeout=20)
pricing.raise_for_status()
catalog = pricing.json()

catalog['regions']['ID']['prices'] = [
    {'pages': 8, 'digital': 15000, 'softcover': 100000, 'hardcover': 150000},
    {'pages': 16, 'digital': 25000, 'softcover': 200000, 'hardcover': 250000},
    {'pages': 24, 'digital': 39000, 'softcover': 340000, 'hardcover': 390000},
    {'pages': 32, 'digital': 49000, 'softcover': 440000, 'hardcover': 490000},
]
catalog['regions']['OTHER']['prices'] = [
    {'pages': 8, 'digital': 100, 'softcover': 1000, 'hardcover': 1500},
    {'pages': 16, 'digital': 195, 'softcover': 1800, 'hardcover': 2500},
    {'pages': 24, 'digital': 295, 'softcover': 2500, 'hardcover': 3900},
    {'pages': 32, 'digital': 395, 'softcover': 3200, 'hardcover': 4900},
]

result = session.put(f'{base_url}/api/admin/pricing', json=catalog, timeout=20)
result.raise_for_status()

db.user_sessions.delete_many({'user_id': user_id})
db.users.delete_many({'user_id': user_id})
client.close()

print('Pricing defaults restored successfully')
