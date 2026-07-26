# Deploy Clarence to clarenceai.live

## What’s already prepared

| File | Purpose |
|------|---------|
| `Dockerfile` | Production container |
| `Procfile` | Render / Heroku-style start |
| `render.yaml` | One-click Render blueprint |
| `fly.toml` | Fly.io app config |

## Option A — Render (recommended if you want a GUI)

1. Push this project to a **GitHub** repo (private is fine).
2. Go to [https://dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service** → connect the repo.
3. Settings:
   - **Runtime:** Python
   - **Build command:** `pip install -e .`
   - **Start command:** `uvicorn motion_bot.web.app:app --host 0.0.0.0 --port $PORT`
4. Environment variables:
   - `MOTION_BOT_PASSWORD` = a strong site password (not the default forever)
   - `MOTION_BOT_SECRET_KEY` = long random string (e.g. `openssl rand -hex 32`)
   - `MOTION_BOT_HTTPS` = `1`
5. Deploy, wait for the service URL (e.g. `https://clarence-xxxx.onrender.com`).

### Point clarenceai.live at Render

In your domain registrar DNS for **clarenceai.live**:

| Type | Name | Value |
|------|------|--------|
| **CNAME** | `@` or root (if supported) | `clarence-xxxx.onrender.com` |
| **CNAME** | `www` | `clarence-xxxx.onrender.com` |

If the registrar won’t CNAME the root domain, use Render’s **custom domain** UI — it shows the exact records (often an **A** record or ALIAS).

Then in Render → your service → **Custom Domains** → add `clarenceai.live` and `www.clarenceai.live` → enable HTTPS.

---

## Option B — Fly.io (CLI)

```bash
export PATH="$HOME/.fly/bin:$PATH"
fly auth login
cd ~/Motion-Bot
fly launch --no-deploy   # accept/create app, use existing fly.toml if prompted
fly secrets set MOTION_BOT_PASSWORD='your-strong-password' \
  MOTION_BOT_SECRET_KEY="$(openssl rand -hex 32)" \
  MOTION_BOT_HTTPS=1
fly deploy
fly certs add clarenceai.live
fly certs add www.clarenceai.live
```

### DNS for Fly

Fly will print records. Typically:

| Type | Name | Value |
|------|------|--------|
| **A** | `@` | Fly IPv4 from `fly ips list` |
| **AAAA** | `@` | Fly IPv6 |
| **CNAME** | `www` | `clarence-ai.fly.dev` (or your app name) |

---

## After DNS propagates

1. Open **https://clarenceai.live**
2. Password page → site password
3. Test: search, generate, drop a `.docx`

DNS can take **5 minutes to a few hours**.

---

## Local check before deploy

```bash
cd ~/Motion-Bot
source .venv/bin/activate
export MOTION_BOT_PASSWORD='test'
export MOTION_BOT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
motion-bot serve --host 0.0.0.0 --port 8000
```

---

## Security notes

- Change `MOTION_BOT_PASSWORD` from the local default.
- Keep the site private (password gate).
- Uploaded templates are stored on the server filesystem — use a paid plan with persistent disk if you need uploads to survive free-tier sleep/redeploys.
