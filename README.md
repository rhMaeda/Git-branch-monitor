# GitHub Branch Monitor

A web dashboard to monitor commits across multiple GitHub branches in near real-time using webhooks, periodic sync, and local storage.

## Features

- Monitor multiple branches
- GitHub API integration
- Real-time updates via webhook (push events)
- Scheduled background sync (reconciliation)
- Web dashboard with auto-refresh
- Branch comparison (ahead/behind)
- Daily commit summary
- Most changed files
- Commit filtering:
  - Only normal commits
  - Only merges
  - All
- Search by text, author, or branch
- Local SQLite storage
- GitHub API rate limit tracking

---

## Tech Stack

- Python 3.10+
- FastAPI
- Jinja2
- SQLite
- APScheduler
- Requests
- HTML
- Bootstrap 5
- JavaScript

---

## Requirements

- Python 3.10+
- GitHub Personal Access Token
- Access to the repository you want to monitor

---

## Project Structure

```bash
app/
  config.py
  db.py
  github_api.py
  main.py
  sync_service.py
  templates/
    index.html
  static/
    app.js
    styles.css

data/
requirements.txt
.env.example
