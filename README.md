<div align="center">

# 📚 StudyTrack

**A neo-brutalist study management app for college students — timers, deadlines, and progress, all in one place.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)

[Live Demo](#-live-demo) · [Features](#-features) · [Setup](#-getting-started) · [Deployment](#-deploying-live) · [Tech Stack](#-tech-stack)

</div>

---

## 🚀 Live Demo

> **Try it instantly — no signup required.**

| | |
|---|---|
| 🔗 **URL** | [web-production-43148.up.railway.app](https://web-production-43148.up.railway.app/) |
| 📧 **Email** | `ananya.krishnan.demo@gmail.com` |
| 🔑 **Password** | `StudyDemo2026!` |

The demo account comes pre-loaded with 6 subjects, 6 assignments, 9 logged study sessions, a file attachment, and a filled-out profile — every page has real data to explore right away. Prefer a blank slate? Just sign up for your own account instead.

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

**🔐 Accounts & Security**
- Signup/login with security-question password recovery (no email infrastructure needed)
- Account lockout after repeated failed attempts
- CSRF protection on every form
- One-way password hashing — never recoverable
- Self-service account deletion

**🏠 Dashboard**
- Today's study time, urgent deadlines, quick stats
- Live session timer badge visible from every page

**📝 Assignments**
- Search, filter, sort, and paginate
- Calendar view color-coded by priority

</td>
<td width="50%" valign="top">

**📖 Subjects**
- Grouped by category, filterable by year
- Bulk import a whole course list at once
- Attach lecture notes (PDF/Word/PPT/images, up to 20MB)

**⏱️ Study Sessions**
- Live stopwatch that keeps running across page navigation
- Post-session effectiveness rating
- Manual entry for sessions logged after the fact

**📊 Progress & Analytics**
- Streaks, completion %, hours/day
- Three interactive charts (Chart.js, bundled — works offline)

**👤 Profile**
- GPA, attendance, and goal tracking
- Dark/light theme toggle
- One-click JSON data export

</td>
</tr>
</table>

Styled throughout with a consistent neo-brutalist design system — bold flat colors, thick borders, hard drop shadows — plus custom 404/403/413/500 error pages.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-Login, Flask-WTF |
| Database | SQLAlchemy ORM — SQLite (local) or Postgres (production) |
| Frontend | Vanilla HTML/CSS/JS — no framework, no build step |
| Charts | Chart.js (bundled locally) |
| Auth | Werkzeug password hashing, CSRF-protected sessions |

---

## 🏁 Getting Started

**1. Install Python 3.9+** if you don't already have it.

**2. Install dependencies and run** — the easy way:
```bash
./run.sh        # Mac/Linux
run.bat         # Windows (double-click, or run from a terminal)
```

Or manually:
```bash
cd study_tracker
pip install -r requirements.txt
python app.py
```

**3.** Open **http://127.0.0.1:5000** in your browser.

**4.** Click **Sign Up**, or log in with the [demo account](#-live-demo) above.

A SQLite database and `.secret_key` file are generated automatically on first run — no manual setup needed for local development.

---

## 📂 Project Structure

```
study_tracker/
├── app.py                     # Flask app: models, auth, all routes
├── requirements.txt
├── Procfile                   # Production start command (Railway/Render)
├── run.sh / run.bat           # One-step launcher scripts
├── .gitignore
├── uploads/                   # Subject note attachments
├── static/
│   ├── favicon.svg
│   ├── css/style.css          # Neo-brutalist styling + theme variables
│   └── js/
│       ├── main.js
│       └── chart.umd.js       # Bundled Chart.js (no internet required)
└── templates/
    ├── landing.html           # Public marketing homepage
    ├── base.html               # Shared layout, nav, timer badge
    ├── login.html / signup.html / forgot_password.html / reset_password.html
    ├── dashboard.html
    ├── assignments.html / assignment_form.html / assignments_calendar.html
    ├── subjects.html / subject_form.html / bulk_import.html
    ├── study_history.html / study_session_form.html / study_timer.html
    ├── progress.html / profile.html
    └── error.html              # 404 / 403 / 413 / 500 pages
```

---

## ☁️ Deploying Live

This app runs unmodified on any host with persistent storage — **Railway, Render, Fly.io, PythonAnywhere, or a VPS all just work**, no extra setup required.

**Deploying to Vercel** needs two extra steps, since serverless functions have a read-only filesystem:

<details>
<summary><strong>Click to expand Vercel setup</strong></summary>

**1. Add a Postgres database** — Vercel project → **Storage** → **Create Database** → **Neon**. This auto-injects a `DATABASE_URL` env var; the app picks it up automatically and falls back to local SQLite when it's not set, so local dev is unaffected.

**2. Set a permanent secret key** — otherwise login sessions get invalidated on every cold start:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Add the output as `STUDYTRACK_SECRET_KEY` in **Vercel → Settings → Environment Variables**, then redeploy.

**Known limitation:** file uploads are saved to local disk and won't persist across serverless instances even with the above fixes. Everything else (accounts, assignments, sessions, progress) is unaffected once Postgres is connected.

</details>

---

## 🔒 Security Notes

- Passwords and security answers are hashed with Werkzeug — never stored or recoverable as plain text.
- Failed login/reset attempts are rate-limited per email address.
- Every form is CSRF-protected via Flask-WTF.
- Back up your data anytime via **Profile → Export Your Data**.

---

## 🗺 Roadmap

Ideas considered but intentionally left out of this version: Pomodoro-style break reminders, automatic GPA calculation from grades, a class timetable with attendance, soft-delete with undo, and a calendar-heatmap streak view.

---

## 📄 License

MIT — free to use, modify, and learn from.

## 👤 Author

**Keith Jackson Rumao**
AI/ML undergraduate · Full-stack & AI developer tooling

[GitHub](https://github.com/Keith10Rumao) · Connect on LinkedIn

