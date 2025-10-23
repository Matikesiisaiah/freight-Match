# SwiftLoad Board (Flask + SQLite)

Single-file load board web app with roles (shipper/trucker/admin), posting loads, bidding, assigning, messaging, and saved loads.

## Quick start (local)

```bash
git clone <your-repo-url> swiftload-board
cd swiftload-board
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
# Open http://127.0.0.1:5000
```

Default admin:
- **email**: `admin@demo.com`
- **password**: `admin123`

## Deploy to Render

1. Create new **Web Service** from this repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn app:app`
4. Instance: free or any size.
5. Add environment variable `SECRET` with a strong secret (optional).

## Deploy to Railway / Fly.io / Heroku

- Start command is the same: `gunicorn app:app`.
- Make sure Python 3.11+ is used.

## Tech stack

- Flask 3, SQLite, inline HTML/CSS
- Gunicorn for production servers

## Database

SQLite file `loadboard.db` is auto-created on first run with tables:
`users`, `loads`, `bids`, `messages`, `saved_loads`.

## GitHub setup

```bash
git init
git add .
git commit -m "Initial commit: SwiftLoad board"
git branch -M main
git remote add origin https://github.com/<your-username>/swiftload-board.git
git push -u origin main
```
