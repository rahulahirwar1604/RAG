# DualRAG — Free Deployment Guide
## Vercel · Render · Qdrant Cloud · Cloudinary

Everything in this guide is **100 % free**. No credit card required for any step
unless you exceed generous free-tier limits (which a personal/portfolio project won't).

---

## What each service does

| Service | Role | Free tier |
|---|---|---|
| **GitHub** | Source of truth, triggers all deploys | Unlimited public repos |
| **Render** | Runs your FastAPI backend (Python) | 512 MB RAM, auto-deploy on push |
| **Vercel** | Hosts your Vite/JS frontend (CDN) | Unlimited bandwidth, global CDN |
| **Qdrant Cloud** | Vector database | 1 GB storage, 1 cluster |
| **Cloudinary** | Stores uploaded PDF/DOCX files as CDN assets | 25 GB storage, 25 GB bandwidth/month |
| **OpenRouter** | One API key → Claude LLM + NVIDIA embeddings | Free credits on signup |
| **NVIDIA Build** | Reranker API | Free tier |

---

## Folder structure (required before deploying)

```
dualrag/                  ← repo root
├── .gitignore
├── render.yaml           ← Render reads this automatically
│
├── backend/              ← Python / FastAPI
│   ├── app.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/
│   │   ├── config.py     ← UPDATED (Claude + Cloudinary settings)
│   │   ├── llm.py        ← UPDATED (Claude via OpenRouter, no Gemini)
│   │   ├── vectorstore.py ← UPDATED (QDRANT_URL for cloud)
│   │   ├── embeddings.py
│   │   ├── memory.py
│   │   └── reranker.py
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── generator.py
│   │   ├── retrieval.py
│   │   ├── chunker.py
│   │   └── parser.py
│   └── api/
│       ├── upload.py     ← UPDATED (Cloudinary backup)
│       ├── query.py
│       ├── documents.py
│       └── health.py
│
└── frontend/             ← Vite / Vanilla JS
    ├── vercel.json       ← Vercel reads this automatically
    ├── vite.config.js    ← UPDATED (proxy + VITE_API_URL)
    ├── .env.local.example
    ├── package.json
    ├── index.html
    └── src/
        ├── main.js
        └── style.css
```

---

## Step 1 — Get your free API keys (15 minutes)

Do this first so you have all keys ready for later steps.

### 1a. OpenRouter (Claude + embeddings)
1. Go to **openrouter.ai** → Sign up (free)
2. Dashboard → **Keys** → **Create Key**
3. Copy the key: `sk-or-v1-xxxx`
4. On the free plan you get $1 credit — enough for hundreds of queries

### 1b. NVIDIA Build (reranker)
1. Go to **build.nvidia.com** → Sign up (free)
2. Dashboard → **API Key** → Generate
3. Copy: `nvapi-xxxx`

### 1c. Qdrant Cloud (vector database)
1. Go to **cloud.qdrant.io** → Sign up (free)
2. **Create Cluster** → Name: `dualrag` → Region: pick nearest → Free tier
3. Once created, click the cluster → copy:
   - **Cluster URL**: `https://xxxx-xxxx.us-east4-0.gcp.cloud.qdrant.io`
   - **API Key**: from the "API Keys" tab

### 1d. Cloudinary (file storage)
1. Go to **cloudinary.com** → Sign up (free)
2. Dashboard shows your:
   - **Cloud Name** (e.g. `dualrag-abc`)
   - **API Key**
   - **API Secret**

---

## Step 2 — Prepare your code (5 minutes)

Replace these three files in your project with the updated versions provided:

| File | What changed |
|---|---|
| `backend/core/config.py` | Removed Gemini, added `QDRANT_URL`, `CLOUDINARY_*` settings |
| `backend/core/llm.py` | Replaced `google-generativeai` with `openai` → OpenRouter → Claude |
| `backend/core/vectorstore.py` | Uses `settings.qdrant_connection` (picks cloud URL vs local) |
| `backend/api/upload.py` | Adds optional Cloudinary backup after ingestion |
| `backend/requirements.txt` | Removed `google-generativeai`, added `cloudinary` |
| `frontend/vite.config.js` | Reads `VITE_API_URL` env var for backend URL |

Also add these new files:
- `render.yaml` (repo root)
- `frontend/vercel.json`
- `.gitignore`

---

## Step 3 — Push to GitHub (2 minutes)

```bash
cd dualrag

git init
git add .
git commit -m "Initial commit — free stack (Claude + Qdrant Cloud + Cloudinary)"

# Create a new repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/dualrag.git
git branch -M main
git push -u origin main
```

---

## Step 4 — Deploy backend on Render (10 minutes)

1. Go to **render.com** → Sign up (free, use GitHub login)
2. Dashboard → **New** → **Web Service**
3. Connect your GitHub repo → Select `dualrag`
4. Render will detect `render.yaml` automatically. Confirm:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
5. Click **Advanced** → **Environment Variables** → Add each key:

```
OPENROUTER_API_KEY      = sk-or-v1-xxxx
OPENROUTER_BASE_URL     = https://openrouter.ai/api/v1
LLM_MODEL               = anthropic/claude-sonnet-4-20250514
EMBEDDING_MODEL         = nvidia/llama-nemotron-embed-vl-1b-v2:free
EMBEDDING_DIMENSIONS    = 2048
NVIDIA_API_KEY          = nvapi-xxxx
QDRANT_URL              = https://xxxx.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY          = your-qdrant-key
QDRANT_COLLECTION       = dualrag_documents
CLOUDINARY_CLOUD_NAME   = your-cloud-name
CLOUDINARY_API_KEY      = your-cloudinary-key
CLOUDINARY_API_SECRET   = your-cloudinary-secret
CORS_ORIGINS            = http://localhost:5173   ← update after Step 5
DEBUG                   = False
```

6. Click **Create Web Service**
7. Wait ~3 minutes for the first build
8. Copy your backend URL: `https://dualrag-backend.onrender.com`
9. Test it:
   ```
   curl https://dualrag-backend.onrender.com/api/health
   # → {"status":"ok"}
   ```

> ⚠️ **Render free tier sleeps after 15 min of inactivity.**  
> First request after sleep takes ~30 seconds to wake up. This is normal.  
> To avoid it: use UptimeRobot (free) to ping `/api/health` every 14 minutes.

---

## Step 5 — Deploy frontend on Vercel (5 minutes)

1. Go to **vercel.com** → Sign up (free, use GitHub login)
2. Dashboard → **Add New Project** → Import `dualrag` repo
3. Vercel detects Vite automatically. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. **Environment Variables** → Add:
   ```
   VITE_API_URL = https://dualrag-backend.onrender.com/api
   ```
5. Click **Deploy**
6. Wait ~1 minute → Get your URL: `https://dualrag.vercel.app`

---

## Step 6 — Update CORS on Render (2 minutes)

Now that you have your Vercel URL, go back to Render:

1. Your service → **Environment** → Edit `CORS_ORIGINS`:
   ```
   https://dualrag.vercel.app,http://localhost:5173
   ```
2. Save → Render auto-redeploys (~1 min)

---

## Step 7 — Verify the full pipeline

```bash
# 1. Health check
curl https://dualrag-backend.onrender.com/api/health

# 2. Open your frontend
open https://dualrag.vercel.app

# 3. Upload a PDF via the UI paperclip button

# 4. Ask a question about the document

# 5. Check Cloudinary dashboard → Media Library
#    You should see the uploaded file under dualrag/
```

---

## Step 8 — Keep Render awake for free (optional but recommended)

Render free tier sleeps after 15 minutes. Use UptimeRobot to prevent this:

1. Go to **uptimerobot.com** → Sign up (free)
2. **Add New Monitor**:
   - Type: HTTP(s)
   - URL: `https://dualrag-backend.onrender.com/api/health`
   - Interval: 14 minutes
3. Done — your backend stays warm 24/7

---

## Auto-deploy on every push

Both Render and Vercel watch your `main` branch. Once set up:

```bash
# Make a change, push — both services redeploy automatically
git add .
git commit -m "Update system prompt"
git push
```

Render: ~2-3 min rebuild. Vercel: ~30 seconds.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `CORS error` in browser | Add Vercel URL to `CORS_ORIGINS` in Render env |
| `Connection refused` on health check | Render is still building — wait 3 min |
| `502 Bad Gateway` on query | Check Render logs → usually a missing env var |
| `Qdrant connection error` | Verify `QDRANT_URL` includes `https://` and no trailing slash |
| `Embedding failed` | Check `OPENROUTER_API_KEY` is set in Render |
| Backend wakes up slowly | Set up UptimeRobot (Step 8) |
| Frontend shows "Disconnected" | Check `VITE_API_URL` in Vercel env — must match Render URL exactly |

---

## Cost summary

| Service | Free tier limit | Will you hit it? |
|---|---|---|
| Render | 750 hrs/month compute | No (1 service = 1 server) |
| Vercel | 100 GB bandwidth/month | No |
| Qdrant Cloud | 1 GB vector storage | ~50,000 document chunks |
| Cloudinary | 25 GB storage, 25 GB bandwidth | No |
| OpenRouter | $1 free credit (~1000 Claude queries) | Add $5 when it runs out |
| NVIDIA Build | Free tier reranking | No |

**Total monthly cost: $0** until your project has real traffic.
