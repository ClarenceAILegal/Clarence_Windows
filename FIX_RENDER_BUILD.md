# Fix: `No such file or directory: 'requirements.txt'`

That error means Render is **not building the folder that contains your app**.

Your Mac project **does** have `requirements.txt` at:

`~/Motion-Bot/requirements.txt`

---

## Fix A (most common) — clear Root Directory

1. Render → your **clarence** service → **Settings**
2. Find **Root Directory**
3. Set it to **empty** (blank) — not `src`, not `app`, not `Motion-Bot` unless the repo is nested
4. **Build Command** (copy exactly):

```bash
pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
```

5. **Start Command**:

```bash
uvicorn motion_bot.web.app:app --host 0.0.0.0 --port $PORT
```

6. **Manual Deploy** → **Clear build cache & deploy**

---

## Fix B — repo structure is nested

On GitHub, open the repo. You should see at the **top level**:

- `requirements.txt`
- `motion_bot/`
- `templates/`
- `README.md`

### Wrong
```
your-repo/
  Motion-Bot/
    requirements.txt
    motion_bot/
```

### Right
```
your-repo/
  requirements.txt
  motion_bot/
  templates/
```

**If it’s nested under `Motion-Bot/`:**

- Either set **Root Directory** to `Motion-Bot`
- Or re-push so files sit at the repo root

---

## Fix C — code never made it to GitHub

On your Mac:

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/Motion-Bot
gh auth login          # if needed
git remote -v          # should show origin
git add -A
git commit -m "Ensure requirements.txt for Render"
gh repo create clarence --private --source=. --remote=origin --push
# or if remote exists:
git push -u origin main
```

Then on GitHub.com open the repo and **confirm `requirements.txt` is visible on the main branch**.

---

## After it builds

1. Open the `*.onrender.com` URL  
2. You should see the blue password page  
3. Then attach **clarenceai.live** under Custom Domains  

If it still fails, paste the **full build log** from the red section (especially the lines above the requirements.txt error).
