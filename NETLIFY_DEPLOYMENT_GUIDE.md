# 🚀 Bot SaaS Dashboard — Netlify & Git Reference Guide

This document serves as the complete technical reference for deploying, maintaining, and updating the **Bot SaaS Dashboard** (`discord-bot2`) on **Netlify** and **GitHub**.

---

## 📌 1. Git Repository Details

| Property | Value |
|---|---|
| **Repository URL** | `https://github.com/Ryl1thX/bot-dashboard.git` |
| **Default Branch** | `main` |
| **Local Workspace** | `/storage/emulated/0/discord-bot2` |
| **Remote Name** | `origin` |

### 🛠️ Common Git Commands for Updates
```bash
# 1. Check current status & modified files
cd /storage/emulated/0/discord-bot2
git status

# 2. Stage all modifications
git add .

# 3. Commit changes with a descriptive message
git commit -m "Update API endpoints and model keys"

# 4. Push directly to GitHub (triggers Netlify auto-deploy)
git push origin main
```

---

## 🌐 2. Netlify Deployment Architecture

Netlify automatically builds and deploys the site on every push to `origin/main`.

### Directory & Build Settings
* **Build Command**: *(Leave empty — static assets + serverless functions)*
* **Publish Directory**: `.`
* **Functions Directory**: `netlify/functions`
* **Node Bundler**: `esbuild`

### `netlify.toml` Routing Rules
```toml
[build]
  publish = "."
  functions = "netlify/functions"

[functions]
  node_bundler = "esbuild"

# Proxy all /api/* calls to Netlify Serverless Functions
[[redirects]]
  from = "/api/*"
  to = "/.netlify/functions/:splat"
  status = 200

# Route Clean URLs
[[redirects]]
  from = "/dashboard"
  to = "/dashboard.html"
  status = 200

[[redirects]]
  from = "/drafting"
  to = "/dashboard.html"
  status = 200

[[redirects]]
  from = "/desk"
  to = "/dashboard.html"
  status = 200

[[redirects]]
  from = "/studio"
  to = "/index.html"
  status = 200

[[redirects]]
  from = "/chat"
  to = "/index.html"
  status = 200

# CORS Headers
[[headers]]
  for = "/*"
  [headers.values]
    Access-Control-Allow-Origin = "*"
    Access-Control-Allow-Methods = "GET, POST, PATCH, DELETE, OPTIONS"
    Access-Control-Allow-Headers = "Content-Type, Authorization, X-User-Id, X-User-Email"
```

---

## 🔑 3. Environment Variables & API Keys Reference

Set these in **Netlify Dashboard** ➡️ **Site configuration** ➡️ **Environment variables** (and in local `.env`):

| Variable Name | Required? | Purpose / Description | Example Format |
|---|---|---|---|
| `GEMINI_KEY` | **Yes** | Google Gemini API (2.0 Flash, Flash-Lite) | `AQ.Ab8RN6Jl-...` or `AIzaSy...` |
| `GROQ_KEY` | **Yes** | Groq Llama 3.3 70B & 8B high-speed inference | `gsk_...` |
| `OPENROUTER_KEY` | Optional | Multi-provider fallback & Vision inference | `sk-or-v1-...` |
| `MISTRAL_KEY` | Optional | Mistral AI provider fallback | `6vKz8...` |
| `FISH_AUDIO_KEY` | Optional | Fish Audio Neural TTS engine | `49bc5066...` |
| `HF_KEY` | Optional | Hugging Face Serverless Inference | `hf_...` |
| `SUPABASE_URL` | **Yes** | Supabase database instance | `https://tdawmkgedbxbjkctylld.supabase.co` |
| `SUPABASE_SERVICE_KEY` | **Yes** | Supabase service_role JWT key (bypass RLS) | `eyJhbGciOi...` |
| `SUPABASE_ANON_KEY` | **Yes** | Supabase anon public JWT key | `eyJhbGciOi...` |
| `DISCORD_TOKEN` | Optional | Discord bot token for bot avatar/info queries | `MTUzMDI4...` |

---

## ⚡ 4. Serverless API Endpoints (`api/` & `netlify/functions/`)

The repository includes serverless functions supporting both Vercel and Netlify:

### 1. `/api/chat` (`chat.js`)
* **Method**: `POST`
* **Payload**: `{ message, bot_id, access_key, model_slots, history, system_prompt, image }`
* **Features**:
  * Multi-provider cascade: **Gemini 2.0 Flash ➜ Groq Llama-3.3-70B ➜ OpenRouter ➜ HuggingFace**.
  * Memory tree context injection & user persona isolation.
  * Image / vision multimodal parsing.

### 2. `/api/bots` (`bots.js`)
* **Methods**: `GET`, `POST`, `PATCH`, `DELETE`
* **Features**:
  * Lists community & user-owned bots from Supabase `user_bots` table.
  * CRUD actions for bot configurations, custom prompts, and model slots.

### 3. `/api/discord_info` (`discord_info.js`)
* **Method**: `GET /api/discord_info?token=...`
* **Features**:
  * Validates Discord Bot Tokens and returns bot name, avatar URL, and ID.

> ⚠️ **Important**: When making changes to any file in `api/`, always copy them to `netlify/functions/`:
> ```bash
> cp api/chat.js netlify/functions/chat.js
> cp api/bots.js netlify/functions/bots.js
> cp api/discord_info.js netlify/functions/discord_info.js
> ```

---

## 🔄 5. Step-by-Step Update Workflow

### Updating API Keys in Netlify:
1. Go to [Netlify Dashboard](https://app.netlify.com/).
2. Select your site ➜ **Site configuration** ➜ **Environment variables**.
3. Edit or add the desired key (e.g. `GEMINI_KEY` or `GROQ_KEY`).
4. Trigger a new deploy (or push a commit) to apply the new keys immediately.

### Updating Frontend & Code:
```bash
cd /storage/emulated/0/discord-bot2

# 1. Make edits to index.html or api/*.js
# 2. Sync to studio.html and netlify/functions
cp index.html studio.html
cp index.html designs/index.html
cp api/*.js netlify/functions/

# 3. Test JavaScript syntax
python3 -c "import re, subprocess; html=open('index.html').read(); [subprocess.run(['node','--check'], input=s.encode(), check=True) for s in re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.DOTALL)]"

# 4. Commit and Push
git add .
git commit -m "feat: update dashboard models and endpoints"
git push origin main
```
