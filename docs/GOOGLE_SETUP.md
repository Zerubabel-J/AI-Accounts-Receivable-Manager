# Google Sheets OAuth setup (one-time, ~5 min)

This is the only step you need to do in a browser. Once done, the backend
talks to your real Google Sheet automatically.

## 1. Create the spreadsheet

1. Open https://sheets.new (creates a new Sheet)
2. Rename it to something like "AR Manager - Demo"
3. Copy the spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/<THIS_PART_IS_THE_ID>/edit
   ```
4. Paste it into `backend/.env`:
   ```
   GOOGLE_SHEETS_ID=<paste here>
   ```

That's the only change to `.env` — the app creates the `invoices`, `payments`,
and `activity` tabs and writes headers automatically on first run.

## 2. Get the OAuth client credentials JSON

You need an OAuth 2.0 "Desktop app" client. This lets the backend pop a browser
window once for consent, then cache the token forever.

1. Go to https://console.cloud.google.com/apis/credentials
   - If prompted, create or pick a project (any name; we don't need billing)
2. Make sure the **Google Sheets API** is enabled:
   - https://console.cloud.google.com/apis/library/sheets.googleapis.com
   - Click **Enable**
3. Configure the OAuth consent screen (if you haven't):
   - https://console.cloud.google.com/apis/credentials/consent
   - User Type: **External**, Create
   - App name: `AR Manager`, support email: your email, developer email: your email, Save
   - Scopes: Save and Continue (no scopes needed here)
   - Test users: add your own Google email, Save and Continue
4. Back at Credentials, click **Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Name: `AR Manager local`
   - Click **Create**
5. In the popup, click **Download JSON**
6. Save it as `backend/credentials.json`

Both `.env` and `credentials.json` are already in `.gitignore` — they will
never be committed.

## 3. First run

Start the backend:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload
```

The first time it makes a Sheets call (e.g. when `seed_demo_data()` runs at
startup) it opens a browser asking for consent. Click **Continue** through the
"unverified app" warning (that's just because we're using a personal app).
The token is cached to `backend/token.json` for all future runs.

## 4. Verify

After the first run, refresh your spreadsheet in the browser. You should see
three tabs (`invoices`, `payments`, `activity`) populated with the seeded data.

## Reset / revoke

To force a fresh OAuth flow, just delete `backend/token.json` and restart.
To revoke the token entirely: https://myaccount.google.com/permissions
