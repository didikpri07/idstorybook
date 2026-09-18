"""Reserve the configured admin email; never promote a self-asserted public signup."""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values(Path(__file__).resolve().parents[1] / 'backend' / '.env')
db = MongoClient(env['MONGO_URL'])[env['DB_NAME']]
output = []
for email in (e.strip().lower() for e in env['ADMIN_EMAILS'].split(',') if e.strip()):
    existing = db.users.find_one({'email': email}, {'_id': 0})
    if existing:
        db.users.update_one({'user_id': existing['user_id']}, {'$set': {'role': 'admin'}})
        output.append({'email': email, 'existing_account': True})
        continue
    token = secrets.token_urlsafe(40)
    db.users.insert_one({'user_id': 'user_' + secrets.token_hex(12), 'email': email, 'name': 'Didik',
        'role': 'admin', 'auth_version': 0, 'created_at': datetime.now(timezone.utc).isoformat(),
        'password_reset': {'token_hash': hashlib.sha256(token.encode()).hexdigest(),
                           'expires_at': datetime.now(timezone.utc) + timedelta(hours=24)}})
    output.append({'email': email, 'existing_account': False,
                   'setup_url': env['FRONTEND_URL'].rstrip('/') + '/reset-password?token=' + token})
path = Path('/root/storybook-tests/admin_setup.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(output))
path.chmod(0o600)
print('Admin account reserved. Private one-time setup details saved server-side; no password or key logged.')