# StudyTrack 📚

> **Heads up:** this copy comes pre-loaded with a fully populated demo account
> so you can explore (or demo for your project submission) immediately —
> see **Demo Account** below for the login. Delete `study_tracker.db` and the
> `uploads/` folder any time you want to start completely fresh instead.

A neo-brutalist web app for tracking college academics and study habits —
built with Python (Flask), SQLite, and vanilla HTML/CSS/JS.

Visiting the app for the first time now shows a public **landing page**
(features, how-it-works, a live momentum/streak showcase, and a final
call-to-action) instead of jumping straight to a login form. "Get Started" /
"Create Free Account" go to Sign Up, and "Sign In" / "I Already Have an
Account" go to the login page. If you're already logged in, visiting `/`
skips the landing page and takes you straight to your dashboard.

## Demo Account

This build includes a working test account with 6 subjects, 6 assignments
(some completed, some pending, one due tomorrow), 9 study sessions spread
across the last week, a subject note attachment, and a filled-out profile —
so every page has real data to show off right away.

```
Email:    ananya.krishnan.demo@gmail.com
Password: FinalPass@789
```

(Security question, in case you want to test "Forgot Password" too:
**"What was the name of your first school?"** → **Greenfield High**)

I ran this account through every feature end-to-end before handing it over:
signup, subjects (manual + bulk import + file attachment), assignments
(search/sort/filter/calendar), the live timer (start → stop → rate → save),
manual session logging, the Progress charts, theme toggle, change password,
updating the security question, the full forgot-password recovery flow, and
data export — all confirmed working against this exact account.


## Features

**Accounts & security**
- Sign up and log in with a `@gmail.com` address (used purely as a login ID —
  no real Google sign-in or email sending involved)
- A security question (set at signup) lets you **reset a forgotten password**
  via "Forgot your password?" on the login page, with no email infrastructure needed
- **Change your password** any time from Profile while logged in
- **Account lockout** after repeated failed login or security-answer attempts,
  to slow down guessing
- **CSRF protection** on every form in the app
- **Delete your account** permanently from a clearly-marked Danger Zone, with
  password confirmation
- Passwords and security answers are stored only as one-way hashes — never
  recoverable, by you or anyone else

**Dashboard**
- Department filter, today's study time, the 3 most urgent deadlines, quick stats
- A persistent badge in the top nav showing a live session timer if one's running,
  visible from every page

**Assignments**
- Add, edit, delete, mark complete
- Search by title, filter by status/subject, sort by due date/priority/title
- Pagination once your list gets long
- A **calendar view** laying deadlines out across the month, color-coded by
  priority, with completed items shown struck through

**Subjects**
- Grouped by category tag (e.g. CORE, AIML), filterable by year level
- Add one at a time or **bulk import** a whole course list via comma-separated text
- **Attach notes** (PDF, Word, PowerPoint, images, up to 20MB each) directly to
  a subject — view, download, or delete them from the edit page

**Study History**
- A real **live stopwatch**: hit Start, it counts up in real time and keeps
  running even if you navigate to other pages — Stop brings up a quick
  effectiveness rating before saving
- A manual-entry form for logging sessions you forgot to time live
- Pagination for your session history

**Progress & Analytics**
- Filterable stats: total hours, streak, completion %, avg/day
- Three real charts (daily study-time trend, subject time allocation, and
  per-subject completion progress), rendered with a bundled copy of Chart.js
  so they work fully offline

**Profile**
- Academic snapshot (GPA, attendance, study hours), goals & targets with
  progress bars, streaks, and an achievement badge shelf
- Dark/light **theme toggle**
- Update your security question any time
- One-click **data export** — a JSON download of your subjects, assignments,
  sessions, and profile info (never your password)

Neo-brutalist styling throughout: bold flat colors, thick black borders, hard
drop shadows, chunky uppercase buttons — plus custom 404/403/413/500 error
pages and a matching favicon.

## Setup

1. **Install Python 3.9+** if you don't already have it.

2. **Install dependencies and run:**

   The easy way — just double-click (Windows) or run (Mac/Linux) the included
   launcher script, which installs dependencies and starts the app for you:
   ```bash
   ./run.sh        # Mac/Linux
   run.bat         # Windows (double-click it, or run from a terminal)
   ```

   Or do it manually:
   ```bash
   cd study_tracker
   pip install -r requirements.txt
   python app.py
   ```

3. Open your browser to **http://127.0.0.1:5000**

4. Click **Sign Up**, create an account with any `@gmail.com` address, set a
   security question you'll remember the answer to, and start adding subjects.

A SQLite database file (`study_tracker.db`) and an `uploads/` folder are created
automatically on first run. A `.secret_key` file is also generated automatically
the first time you run the app — it keeps your login sessions valid across
restarts. Don't delete it or everyone will be logged out (it's harmless to
regenerate, just mildly annoying).

## Deploying live (e.g. Vercel)

**The short version: this app needs two things to work on a serverless host
like Vercel that it doesn't need locally — a real database, and a persistent
secret key. Without them it will crash or silently misbehave, and that's not
a bug in your deployment, it's how serverless hosting works everywhere.**

### Why local SQLite doesn't work on Vercel

Vercel runs your app as a serverless function: every request can be handled
by a *different*, freshly-booted container with a blank, mostly read-only
filesystem. A local file like `study_tracker.db` can't be written to (that's
the "attempt to write a readonly database" error), and even if it could,
each container would have its own separate copy — so a signup on one request
might just vanish on the next. This isn't a Vercel bug or a misconfiguration;
Vercel's own docs are explicit that SQLite isn't supported for this reason.
The fix is a real hosted database that every request connects to over the
network instead of reading from local disk.

### 1. Add a Postgres database

This app already supports Postgres out of the box — it just needs a
connection string. The easiest path if you're on Vercel:

1. In your Vercel project, go to the **Storage** tab → **Create Database** →
   choose the **Neon** (Postgres) integration → follow the prompts.
2. This automatically adds a `DATABASE_URL` environment variable to your
   project — you don't need to copy/paste anything.
3. Redeploy. On the next cold start, the app will connect to Postgres and
   create all its tables automatically (via `db.create_all()`).

Prefer to use your own Postgres (e.g. a free Neon.tech or Supabase project
you set up yourself)? Just add a `DATABASE_URL` environment variable in
**Vercel → Settings → Environment Variables** with your connection string,
for all three environments (Production, Preview, Development).

The app reads `DATABASE_URL` (or `POSTGRES_URL`) automatically and falls
back to local SQLite only when neither is set — so local development with
`python app.py` is completely unaffected by any of this.

### 2. Set a permanent secret key

Without this, the app still works, but the key used to sign login sessions
regenerates on every cold start — meaning people can get logged out
unpredictably, sometimes mid-session. Set it once and forget it:

1. Generate a random key locally: `python -c "import secrets; print(secrets.token_hex(32))"`
2. In **Vercel → Settings → Environment Variables**, add `STUDYTRACK_SECRET_KEY`
   with that value, for all environments.
3. Redeploy.

### 3. Known limitation: file uploads won't persist

Subject notes (PDF/Word/PowerPoint attachments) are saved to local disk,
which — same as the database — doesn't persist or share across serverless
instances. After the fixes above, uploading a note **won't crash** the app
anymore, but the file itself will likely be gone by the time you try to
download it on a later request. Everything else (subjects, assignments,
study sessions, progress charts, login, etc.) is unaffected, since that's
all in Postgres now. If you want uploads to actually persist on Vercel, the
next step is object storage (e.g. Vercel Blob) — that's a separate, larger
change from a database migration, so it's not included here, but ask if you
want it added.

### Deploying somewhere else instead

If you'd rather avoid this whole class of problem, hosts that give you a
real persistent disk (Render, Railway, Fly.io, PythonAnywhere, or a plain
VPS) will run this app completely unmodified — SQLite and local file
uploads both just work there, no environment variables required. Vercel is
great for static/Next.js sites but is fundamentally serverless-only, which
is why a traditional database-backed app like this needs the extra setup
above specifically on that platform.

## Suggested first steps in the app

1. **Sign up** with a Gmail address, a password, and a security question/answer
   — this is what lets you reset your password later if you forget it, since
   there's no real email sent. Don't lose the answer!
2. Go to **Subjects → Add Subject** (or **Bulk Import** to paste in your whole
   course list at once, format: `Name, Category, Credits, Year Level`). While
   adding or editing a subject you can also attach lecture notes, PDFs, or
   slides — they show up as a 📎 chip on the subject card.
3. Go to **Assignments → New Assignment** to log your coursework and due dates,
   or switch to **Calendar View** to see them laid out across the month.
4. Use **Study History → Start New Session**, pick a subject, and hit **Start
   Timer** — it counts up live and keeps running even if you navigate to other
   pages (you'll see it in the top-right badge). Hit **Stop**, rate how focused
   you were, and it's saved automatically. Already studied earlier? Use the
   "log a past session manually" link instead.
5. Check **Progress** to see your trends, streaks, and charts of where your time
   and assignment-completion stand per subject.
6. Visit **Profile** to fill in your GPA, attendance, and weekly study targets,
   change your password, update your security question, export your data, and
   flip the **theme toggle** between dark and light mode.

## Project structure

```
study_tracker/
├── app.py                    # Flask app: models, auth, all routes
├── requirements.txt
├── run.sh / run.bat           # One-step launcher scripts (Mac/Linux, Windows)
├── .gitignore
├── uploads/                  # Subject note attachments (created automatically)
├── .secret_key                # Auto-generated session signing key (don't delete)
├── static/
│   ├── favicon.svg
│   ├── css/style.css          # Neo-brutalist styling + dark/light theme variables
│   └── js/
│       ├── main.js            # Live clock, delete confirmations, chart helpers
│       └── chart.umd.js        # Bundled Chart.js (no internet required)
└── templates/
    ├── landing.html            # Public marketing homepage, served at /
    ├── base.html               # Shared layout, nav, flash messages, timer badge
    ├── login.html / signup.html
    ├── forgot_password.html / reset_password.html
    ├── dashboard.html
    ├── assignments.html / assignment_form.html / assignments_calendar.html
    ├── subjects.html / subject_form.html / bulk_import.html
    ├── study_history.html / study_session_form.html (manual entry)
    ├── study_timer.html        # Live stopwatch flow (idle/running/review)
    ├── progress.html
    ├── profile.html
    └── error.html              # 404 / 403 / 413 / 500 pages
```

## Security notes

- Passwords and security answers are hashed with Werkzeug's
  `generate_password_hash` — one-way, never recoverable as plain text by
  anyone, including you as the developer.
- Failed login and password-reset attempts are rate-limited per email address
  (in-memory, resets on server restart — that's fine for personal/local use).
- Every form submission is protected against CSRF via Flask-WTF.
- If you ever want to back up your account data, use **Profile → Export Your
  Data**, or back up the whole `study_tracker.db` file. Avoid pulling
  individual fields like password hashes into separate plain files.

## What's intentionally not included

A few ideas came up while building this that didn't make the cut for this
version, on purpose — they're genuinely optional rather than missing pieces:
Pomodoro-style break reminders, automatic GPA calculation from assignment
grades, a class timetable with attendance tied to real sessions, soft-delete
with undo, and a calendar-heatmap view of your study streak. All would be
reasonable follow-ups if you want them later.

## Notes

- This uses Flask's built-in development server locally, which is fine for
  personal/local use. For a real deployment (Vercel or otherwise), see
  **Deploying live** above — it covers the database, secret key, and file
  storage caveats that a serverless host needs that local dev doesn't.
- Subject notes are saved under `uploads/<your-user-id>/` on disk; only you
  can download or delete your own files.
- Chart.js is bundled locally in `static/js/`, so the Progress charts work
  without an internet connection.
- If you're upgrading from an earlier version of this app, delete the old
  `study_tracker.db` file before running — the database schema has changed
  several times (new columns for the live timer, security question, etc., plus
  a new table for subject notes) and SQLite won't add them automatically to
  an existing file.
