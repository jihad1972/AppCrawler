# 🤖 AppCrawler

**AI-Powered Android App Screen Capture & Documentation Tool**

AppCrawler autonomously navigates and analyzes Android mobile apps using **Gemini Vision AI** and **pHash deduplication**, delivering a searchable, exportable screenshot library — essentially letting teams *"build your own Mobbin"* in-house.

![Home Page](https://img.shields.io/badge/Status-Active-brightgreen) ![License](https://img.shields.io/badge/License-MIT-blue)

---

## ✨ Features

- 🤖 **AI-Powered Exploration** — Gemini Vision AI navigates every screen and flow
- 📱 **Automatic Screenshots** — Captures every unique screen with smart deduplication (pHash)
- ⏸️ **Pause / Resume / Stop** — Full crawl lifecycle controls
- ⏱️ **Live ETA** — Real-time progress, elapsed time, and estimated completion
- 🧠 **UX Analysis Ready** — Build your own Mobbin-style library
- ⚡ **Real-Time Monitoring** — WebSocket-powered live screen preview and action log
- 🎨 **Premium Dark UI** — Glassmorphism design with micro-animations

## 🏗️ Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│   React + Vite  │ ◄────────────────► │  FastAPI Backend  │
│   (Frontend)    │     REST API       │                  │
└─────────────────┘                    ├──────────────────┤
                                       │  Gemini Vision   │
                                       │  Appium + ADB    │
                                       │  pHash Dedup     │
                                       └──────┬───────────┘
                                              │
                                       ┌──────▼───────────┐
                                       │ Android Emulator  │
                                       └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+
- **Python** 3.9+
- **Android Studio** + AVD (emulator)
- **Appium** (`npm install -g appium && appium driver install uiautomator2`)
- **Gemini API Key** ([Get one here](https://aistudio.google.com/apikey))

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/AppCrawler.git
cd AppCrawler

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure

```bash
export GEMINI_API_KEY="your-api-key-here"
export ANDROID_HOME="$HOME/Library/Android/sdk"  # auto-detected on macOS
```

### 3. Run

```bash
# Terminal 1: Backend
cd backend && source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Appium (when ready to crawl)
appium
```

Open **http://localhost:5173** and start crawling!

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/devices` | List connected devices |
| POST | `/api/crawl/start` | Start a crawl |
| POST | `/api/crawl/{id}/pause` | Pause crawl |
| POST | `/api/crawl/{id}/resume` | Resume crawl |
| POST | `/api/crawl/{id}/stop` | Stop crawl |
| GET | `/api/crawl/{id}/status` | Crawl status + ETA |
| GET | `/api/crawl/{id}/screenshots` | List screenshots |
| GET | `/api/crawls` | List all sessions |
| POST | `/api/upload-apk` | Upload & install APK |
| WS | `/ws/crawl/{id}` | Real-time crawl events |

## 🗺️ Roadmap

- [x] **Phase 0** — MVP (crawl engine, AI vision, full UI)
- [x] **Phase 1** — Pause/Resume, ETA, screen-settle detection
- [ ] **Phase 2** — AI screen labeling, flow graph visualization
- [ ] **Phase 3** — ZIP/PDF export, SQLite persistence
- [ ] **Phase 4** — Multi-user, cloud deployment, iOS support

## 📄 License

MIT
