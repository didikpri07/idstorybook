# Auth Testing Playbook — Kids Storybook

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: '',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Test /auth/me with Bearer token
curl -X GET "$API_URL/api/auth/me" -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test protected /api/stories
curl -X GET "$API_URL/api/stories" -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test admin endpoint (no auth needed)
curl -X GET "$API_URL/api/admin/orders"
```

## Step 3: Browser Testing (Playwright)
```python
await page.context().add_cookies([{
    "name": "session_token",
    "value": "YOUR_SESSION_TOKEN",
    "domain": "storybook-magic-29.preview.emergentagent.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None"
}])
await page.goto("https://narrative-id.preview.emergentagent.com/dashboard")
```

## Checklist
- [ ] User doc has `user_id` field
- [ ] Session `user_id` matches user's `user_id`
- [ ] GET /api/auth/me returns user (not 401)
- [ ] Dashboard loads for authenticated user
- [ ] /create redirects unauthenticated users to /login
- [ ] /checkout redirects unauthenticated users to /login
- [ ] Admin page calls /api/admin/orders (no auth needed)
- [ ] Storybook viewer is public
- [ ] AuthCallback processes #session_id= and redirects to /dashboard
