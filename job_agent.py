"""
LinkedIn Dubai Job Agent
Fetches fresh Finance/Business job postings via RapidAPI and appends new ones to Google Sheets.
"""

import os
import json
import base64
import tempfile
import requests
import gspread
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials

# ── Config ──────────────────────────────────────────────────────────────────

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
SHEET_ID = os.environ["SHEET_ID"]          # Google Sheet ID from the URL
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]  # base64-encoded service-account JSON

SEARCH_KEYWORDS = [
    "Financial Analyst",
    "Business Analyst",
    "Investment Banker",
    "Consultant",
    "Finance Manager",
    "Corporate Finance",
]

LOCATION = "Dubai"
RESULTS_PER_KEYWORD = 10   # max per search (RapidAPI free tier allows up to 10)
SHEET_NAME = "Jobs"

HEADERS = [
    "Job ID", "Title", "Company", "Location", "Date Posted",
    "Job URL", "Employment Type", "Seniority", "Date Added"
]

# ── Google Sheets ────────────────────────────────────────────────────────────

def get_sheet():
    creds_json = json.loads(base64.b64decode(GOOGLE_CREDENTIALS).decode())
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SHEET_ID)
    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)
    return ws


def get_existing_ids(ws):
    try:
        col = ws.col_values(1)  # "Job ID" column
        return set(col[1:])     # skip header
    except Exception:
        return set()


def append_jobs(ws, rows):
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"  → Appended {len(rows)} new job(s)")
    else:
        print("  → No new jobs to add")

# ── RapidAPI LinkedIn Jobs ───────────────────────────────────────────────────

RAPIDAPI_HOST = "linkedin-jobs-search.p.rapidapi.com"

def fetch_jobs(keyword: str) -> list[dict]:
    url = "https://linkedin-jobs-search.p.rapidapi.com/"
    payload = {
        "search_terms": keyword,
        "location": LOCATION,
        "page": "1",
        "fetch_full_text": "no",
    }
    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception as e:
        print(f"  [WARN] Failed fetching '{keyword}': {e}")
        return []


def job_to_row(job: dict) -> list:
    return [
        job.get("job_id", ""),
        job.get("job_title", ""),
        job.get("company_name", ""),
        job.get("job_location", ""),
        job.get("posted_date", ""),
        job.get("linkedin_job_url_cleaned", job.get("job_url", "")),
        job.get("job_employment_type", ""),
        job.get("job_seniority_level", ""),
        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ]

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting LinkedIn Dubai Job Agent")
    ws = get_sheet()
    existing_ids = get_existing_ids(ws)
    print(f"  Existing jobs in sheet: {len(existing_ids)}")

    new_rows = []
    seen_this_run = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"  Searching: '{keyword}' in {LOCATION}")
        jobs = fetch_jobs(keyword)
        fresh = 0
        for job in jobs:
            job_id = str(job.get("job_id", ""))
            if not job_id or job_id in existing_ids or job_id in seen_this_run:
                continue
            seen_this_run.add(job_id)
            new_rows.append(job_to_row(job))
            fresh += 1
        print(f"    Found {len(jobs)} postings, {fresh} new")

    append_jobs(ws, new_rows)
    print(f"Done. Total new jobs added: {len(new_rows)}")


if __name__ == "__main__":
    main()
