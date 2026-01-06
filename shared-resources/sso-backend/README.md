# UnifAI SSO Backend

This service handles authentication for the UnifAI platform, supporting both:
- **Internal users**: Red Hat SSO (Keycloak) for employees
- **External users**: Local username/password authentication

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SSO Backend                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   AuthManager       │    │   LocalAuthManager              │ │
│  │   (Keycloak SSO)    │    │   (Username/Password)           │ │
│  │                     │    │                                 │ │
│  │  /api/auth/login    │    │  /api/auth/local/login          │ │
│  │  /api/auth/callback │    │  /api/auth/local/signup         │ │
│  │  /api/auth/logout   │    │  /api/auth/local/refresh        │ │
│  │  /api/auth/user     │    │  /api/auth/local/check-username │ │
│  │  /api/auth/refresh  │    │  /api/auth/local/check-email    │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
│                                                                  │
│  Unified Session Format:                                         │
│  {                                                               │
│    username, email, name, sub,                                   │
│    session_created_at, session_expires_at, token_expires_at,     │
│    auth_provider: "local" | "keycloak"                           │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Endpoints

### SSO (Keycloak) Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | GET | Initiates Keycloak OAuth flow |
| `/api/auth/callback` | GET | OAuth callback handler |
| `/api/auth/logout` | POST | Logout user |
| `/api/auth/user` | GET | Get current user info |
| `/api/auth/refresh` | POST | Refresh access token |

### Local Auth Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/local/signup` | POST | Register new external user |
| `/api/auth/local/login` | POST | Login with username/password |
| `/api/auth/local/refresh` | POST | Refresh local session |
| `/api/auth/local/check-username` | GET | Check username availability |
| `/api/auth/local/check-email` | GET | Check email availability |

## Local User Registration

### Request
```json
POST /api/auth/local/signup
{
  "username": "johndoe",
  "email": "john@example.com",
  "name": "John Doe",
  "password": "SecurePass123!"
}
```

### Password Requirements
- At least 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (!@#$%^&*(),.?":{}|<>)

### Response
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "username": "johndoe",
    "email": "john@example.com",
    "name": "John Doe",
    "sub": "abc123..."
  }
}
```

## Local User Login

### Request
```json
POST /api/auth/local/login
{
  "identifier": "johndoe",  // username or email
  "password": "SecurePass123!"
}
```

### Response
```json
{
  "authenticated": true,
  "message": "Login successful",
  "user": {
    "username": "johndoe",
    "email": "john@example.com",
    "name": "John Doe",
    "sub": "abc123...",
    "session_created_at": 1234567890,
    "session_expires_at": 1234607890,
    "token_expires_at": 1234571490,
    "auth_provider": "local"
  }
}
```

## Dependencies

```
flask
flask-cors
requests
Authlib
PyJWT
python-dotenv
pydantic
pydantic-settings
bcrypt
pymongo
```

## Configuration

Environment variables (or config file):
- `mongodb_ip`: MongoDB server IP (default: localhost)
- `mongodb_port`: MongoDB server port (default: 27017)
- `keycloak_base_url`: Keycloak server URL
- `client_id`: Keycloak client ID
- `client_secret`: Keycloak client secret
- `keycloak_realm`: Keycloak realm name
- `frontend_url`: Frontend application URL
- `backend_env`: Environment (development/production)

## SSO Flow (Keycloak)

![Alt text](unifai_sso.png "unifai SSO flow")

The flowchart was created using [sequencediagram.org](https://sequencediagram.org/):

```
title Unifai SSO process

User->Nginx: get UI client files (frontend_url)
Nginx->User: send UI client files
note over User,Nginx:Client automaticaly send API call to start login process
User->Nginx: frontend_url/api3/auth/login
Nginx->User: redirect to sso-be-url/api/auth/login
User->sso-be: sso-be-url/api/auth/login
sso-be->User: redirect to RH-SSO
note over User,sso-be:redirect url: sso-be/api/callback
User->RH-sso: login process
RH-sso->User: redirect to sso-be/api/callback
sso-be->User: redirect to frontend_url?auth=success
User->Nginx: browse pages (frontend_url/api1 | frontend_url/api2)
```

## Database Schema

Local users are stored in MongoDB:
- **Database**: UnifAI
- **Collection**: local_users

```json
{
  "sub": "unique-user-id",
  "username": "johndoe",
  "email": "john@example.com",
  "name": "John Doe",
  "password_hash": "bcrypt-hashed-password",
  "auth_provider": "local",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
}
```

Indexes:
- `username` (unique)
- `email` (unique)
- `sub` (unique)
