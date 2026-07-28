# Pepper Clinical Infinity V6 — Server Deployment Guide
© 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved

A production-grade, secure FastAPI backend + web frontend for the
Pepper Clinical autism therapy platform. Ready to upload to any server.

---

## What's Inside

```
pepper_server/
├── app/
│   ├── main.py              FastAPI app + all security middleware
│   ├── api/
│   │   ├── auth.py          Trial / Login / Refresh (JWT + PIN)
│   │   ├── children.py      Child profiles (encrypted names)
│   │   ├── sessions.py      Sessions + 100K task generator + stats
│   │   └── deps.py          Auth dependency (current user)
│   ├── core/
│   │   ├── config.py        Settings (env-driven)
│   │   ├── security.py      bcrypt · JWT · Fernet encryption · rate limiter
│   │   └── database.py      SQLAlchemy ORM + connection pooling
│   ├── models/schemas.py    Pydantic request/response validation
│   ├── services/task_generator.py  100K+ ABA/DTT/TEACCH/ESDM/PRT/VB tasks
│   └── static/index.html    Web frontend (single-page app)
├── deploy/
│   ├── pepper.service       systemd unit (hardened)
│   ├── Caddyfile            Caddy reverse proxy (auto-HTTPS)
│   ├── nginx.conf           Nginx alternative
│   ├── Dockerfile           Container image
│   └── gunicorn_conf.py     Gunicorn production config
├── requirements.txt
├── .env.example
└── gunicorn_conf.py
```

## Security Features (built in)

- **bcrypt** PIN hashing (12 rounds) — no plaintext PINs stored
- **JWT** access + refresh tokens (HS256)
- **Fernet (AES)** field-level encryption — child names/diagnoses encrypted at rest
- **Rate limiting** — global 60/min, login 5/min with 15-min lockout
- **Brute-force protection** on login
- **Security headers** — HSTS, CSP, X-Frame-Options, nosniff
- **CORS + TrustedHost** restrictions
- **Audit log** table
- **Input validation** via Pydantic on every endpoint
- **Docs disabled** in production (no /docs leak)
- **Non-root** Docker user + systemd hardening

---

## Quick Start (local)

```bash
cd pepper_server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit secrets
uvicorn app.main:app --reload
# → http://127.0.0.1:8000        (API)
# → http://127.0.0.1:8000/app    (web frontend)
# → http://127.0.0.1:8000/docs   (dev only)
```

## Generate Secrets

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```
Paste these into `.env`.

---

## Production Deploy (Ubuntu + Caddy — recommended)

```bash
# 1. Create user + upload code
sudo adduser --system --group pepper
sudo cp -r pepper_server /home/pepper/
cd /home/pepper/pepper_server

# 2. Virtualenv + deps
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. Configure
cp .env.example .env
nano .env                      # set ENV=production + real secrets + domain

# 4. systemd service
sudo cp deploy/pepper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pepper
sudo systemctl status pepper

# 5. Caddy (auto-HTTPS)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/yourdomain.com/YOUR_REAL_DOMAIN/' /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

Your API is now live at `https://YOUR_DOMAIN` with auto-renewed TLS.

## Production Deploy (Docker)

```bash
cd pepper_server
docker build -f deploy/Dockerfile -t pepper-v6 .
docker run -d --name pepper \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  pepper-v6
```

---

## Switch to PostgreSQL (recommended for scale)

```bash
pip install psycopg2-binary
# in .env:
DATABASE_URL=postgresql://pepper:STRONG_PASS@localhost:5432/pepper
```
Tables are created automatically on first start.

---

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET  | /health | – | Health check |
| POST | /api/auth/trial | – | Start 15-day trial → returns PIN |
| POST | /api/auth/login | – | Login with email + PIN → tokens |
| POST | /api/auth/refresh | – | Refresh access token |
| GET  | /api/children | ✓ | List children |
| POST | /api/children | ✓ | Add child |
| DELETE | /api/children/{id} | ✓ | Delete child |
| POST | /api/sessions/start | ✓ | Start therapy session |
| POST | /api/sessions/tasks/generate | ✓ | Generate adaptive tasks |
| POST | /api/sessions/end | ✓ | End session + save stats |
| GET  | /api/sessions/history/{child_id} | ✓ | Session history |
| GET  | /api/sessions/stats/{child_id} | ✓ | Child stats + skills |

---

## Maintenance

```bash
sudo systemctl status pepper       # check service
sudo journalctl -u pepper -f       # live logs
sudo systemctl restart pepper      # restart after changes
curl https://YOUR_DOMAIN/health    # verify running
tail -f logs/pepper.log            # app logs
```

---

© 2026 Lamya Fadlulmola Hamed Ali · HIPAA/GDPR-ready architecture
