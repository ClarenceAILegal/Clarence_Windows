# Launch Clarence on Render → clarenceai.live

Do these steps in order. About 15–30 minutes (plus DNS wait).

---

## 1. Put the code on GitHub

### A. Log in to GitHub CLI (one time)

In Terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
gh auth login
```

Choose:

- **GitHub.com**
- **HTTPS**
- **Login with a web browser**
- Complete the browser prompt

### B. Create repo and push

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/Motion-Bot
git add -A
git status
git commit -m "Prepare for Render deploy" || true
gh repo create clarence --private --source=. --remote=origin --push
```

If the repo already exists:

```bash
git remote add origin https://github.com/YOUR_USERNAME/clarence.git
git push -u origin main
```

Copy the repo URL (e.g. `https://github.com/you/clarence`).

---

## 2. Create the Render web service

1. Open [https://dashboard.render.com](https://dashboard.render.com) and sign up / log in (GitHub login is easiest).
2. **New +** → **Web Service**
3. **Connect** your GitHub account if asked, then select the **clarence** repo.
4. Settings:

| Field | Value |
|--------|--------|
| Name | `clarence` |
| Region | Oregon (or closest) |
| Runtime | **Python 3** |
| Branch | `main` |
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt && pip install -e .` |
| Start Command | `uvicorn motion_bot.web.app:app --host 0.0.0.0 --port $PORT` |
| Instance type | **Free** |

5. **Environment** (add these):

| Key | Value |
|-----|--------|
| `MOTION_BOT_PASSWORD` | your strong site password |
| `MOTION_BOT_SECRET_KEY` | paste output of `openssl rand -hex 32` |
| `MOTION_BOT_HTTPS` | `1` |
| `PYTHON_VERSION` | `3.12.8` |

6. Click **Create Web Service** and wait until status is **Live**.
7. Open the free URL (something like `https://clarence-xxxx.onrender.com`) and confirm the blue password page loads.

---

## 3. Attach clarenceai.live

1. In Render → your **clarence** service → **Settings** → **Custom Domains**
2. Add:
   - `clarenceai.live`
   - `www.clarenceai.live` (optional)
3. Render will show **exact DNS records**. Use those — not a guess.

### Typical DNS (confirm in Render UI)

In the DNS panel where you bought **clarenceai.live**:

**If Render shows a CNAME for the root:**

| Type | Name/Host | Value / Target |
|------|-----------|----------------|
| CNAME | `@` or blank or `clarenceai.live` | `clarence-xxxx.onrender.com` |
| CNAME | `www` | `clarence-xxxx.onrender.com` |

**If root CNAME isn’t allowed**, Render may ask for an **A** record or **ALIAS/ANAME** — copy what Render displays.

4. Save DNS. Wait 5–60 minutes (sometimes longer).
5. In Render, wait until the domain shows **Verified** / certificate **Issued**.
6. Open **https://clarenceai.live**

---

## 4. Smoke test on the live site

1. Password page (blue + lattice)
2. Log in
3. Ask for a motion (chat)
4. Drop a `.docx` if no template match
5. Generate a sample motion

---

## Notes

- **Free tier sleeps** after idle time; first load can take ~30–60s.
- **Uploads** live on the server disk; free instances can lose files on redeploy/sleep. For permanent template storage later, add a Render **persistent disk** or object storage.
- Keep `MOTION_BOT_PASSWORD` private.

---

## If something fails

| Symptom | Fix |
|---------|-----|
| Build fails | Check Render logs; ensure `requirements.txt` and `motion_bot/` are in the repo |
| Site 502 | Wait for cold start; check start command uses `$PORT` |
| Domain not working | Re-check DNS against Render’s custom domain page; wait for SSL |
| Login cookie issues | Ensure `MOTION_BOT_HTTPS=1` and you’re on `https://` |

When GitHub login is done (`gh auth login`), say **“repo is ready”** and I can push/deploy commands from here if you want.
