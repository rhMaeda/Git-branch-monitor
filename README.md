# GitHub Branch Monitor

A web dashboard to monitor commits across multiple GitHub branches in near real-time using webhooks, periodic sync, and local storage.

---

## 🚀 Features

- Monitor multiple branches
- Real-time updates via GitHub webhook
- Scheduled background sync
- Branch comparison (ahead / behind)
- Daily commit summary
- Most changed files
- Commit filters:
  - Only normal commits
  - Only merges
  - All
- Search by author, branch, or message
- SQLite database (no setup needed)
- GitHub API rate limit tracking

---

## 📦 Requirements

- Python 3.10+
- GitHub repository access
- GitHub Personal Access Token

---

# 🧭 Step-by-Step Installation

---

## 🪟 Windows

### 1. Clone or download the project

git clone https://github.com/YOUR_USER/YOUR_REPO.git  
cd YOUR_REPO  

### 2. Create virtual environment

python -m venv .venv  
.venv\Scripts\activate  

### 3. Install dependencies

pip install -r requirements.txt  

### 4. Create `.env` file

copy .env.example .env  

### 5. Configure `.env`

Example:

GITHUB_OWNER=your-username-or-org  
GITHUB_REPO=your-repo-name  
GITHUB_TOKEN=your-token  
WEBHOOK_SECRET=your-secret  

MONITORED_BRANCHES=main,develop  
DEFAULT_COMPARE_BASE=main  

### 6. Run the application

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload  

### 7. Open in browser

http://127.0.0.1:8000  

---

## 🐧 Linux / 🍎 macOS

git clone https://github.com/YOUR_USER/YOUR_REPO.git  
cd YOUR_REPO  

python3 -m venv .venv  
source .venv/bin/activate  

pip install -r requirements.txt  

cp .env.example .env  
nano .env  

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload  

---

## 🔑 GitHub Token

Create at:  
https://github.com/settings/tokens  

Permissions required:

- Contents: Read  
- Metadata: Read  

---

## 🔔 Webhook Setup

URL:

http://YOUR_SERVER:8000/api/github/webhook  

Content-Type:

application/json  

Event:

push  

---

## ▶️ Usage

1. Start the application  
2. Push commits to your repository  
3. Open the dashboard  

---

## 🔎 Commit Filters

- Only normal commits  
- Only merges  
- All  

---

## 🗃 Database

SQLite database is automatically created at:

./data/monitor.db  

---

## 🚀 Production

uvicorn app.main:app --host 0.0.0.0 --port 8000  

---

## 🔐 Security

- Do not commit `.env`  
- Do not expose your GitHub token  
- Use minimal permissions  

---

## 📂 .gitignore

.env  
.venv/  
__pycache__/  
*.pyc  
data/*.db  

---

## 📄 License

MIT
