"""Copy the provided runtime TEST key into backend-only configuration without logging it."""
import os
from pathlib import Path
from dotenv import dotenv_values, set_key

env_path = Path(__file__).resolve().parents[1] / 'backend' / '.env'
existing = dotenv_values(env_path)
if existing.get('STRIPE_API_KEY'):
    print('Existing payment configuration preserved.')
else:
    key = os.environ['STRIPE_API_KEY']
    if not key.startswith('sk_test_'):
        raise RuntimeError('Only a Stripe test key can be configured in this phase.')
    set_key(str(env_path), 'STRIPE_API_KEY', key)
    print('Stripe test configuration saved server-side; key value not displayed.')