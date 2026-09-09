# IARE Lake — Attendance Register & Smart Timetable Documentation

> Reference document saved in `test attendance/` for future development and reference.

---

## 1. Overview
This module scrapes official Samvidha pages to generate:
1. **Real-time Attendance Register** (Date $\times$ Subject Matrix & Daily Period 1–6 Timeline)
2. **Smart Student Timetable** (Weekly Schedule Matrix with 100% Course & Faculty Directory)
3. **Token-Based Sharing System with Privacy Controls** (Friends-Only / Public / Private with zero password leak)

---

## 2. Scraping Strategy & URLs

| Component | Source URL | Method | Data Extracted |
|---|---|---|---|
| **Authentication** | `https://samvidha.iare.ac.in/index.php` $\rightarrow$ `checkUser.php` | GET + POST | Dynamic CSRF meta token & authenticated session |
| **Attendance Register** | `https://samvidha.iare.ac.in/home?action=course_content` | GET | All course banners, lecture rows, dates, periods 1–6, topics, PPT links, YouTube links, status |
| **Student Timetable** | `https://samvidha.iare.ac.in/home?action=TT_std` | GET + POST | AY, Section, Mon–Sat grid, Room numbers, Faculty IDs, Bell timings |

---

## 3. Endpoints in `app.py`

### 1. `POST /api/attendance-register`
- **Request**: `{ "roll": "...", "password": "..." }`
- **Output**:
  - `subjects`: List of all 11 courses with `totalHeld`, `totalPresent`, `totalAbsent`, `%`
  - `availableMonths`: Filter list (e.g. `["Aug 2026", "Jul 2026"]`)
  - `summary`: Overall percentage, total conducted, attended, missed
  - `dates`: Sorted descending (`YYYY-MM-DD`, `dateDisplay`, `daySummary`, `records`, `periodsTimeline`)

### 2. `POST /api/timetable`
- **Request**: `{ "roll": "...", "password": "..." }`
- **Output**:
  - `academicYear`, `branchSection`, `bellTimings`
  - `subjectsDirectory`: All 11 registered courses (`THEORY` & `LAB`) with code, name, short code, staff name, staff ID
  - `schedule`: Monday–Saturday weekly schedule with clean period chips, room numbers, and faculty

### 3. `POST /api/share/create`
- **Request**: `{ "roll": "...", "password": "...", "privacy": "friends"|"public"|"private", "permissions": {...} }`
- **Output**: Generates a unique token ID (`iare_...`) and stores a sanitized snapshot with configured permissions.

### 4. `GET /api/share/<token_id>`
- **Output**: Returns the shared register & timetable in read-only mode without requiring any credentials.

### 5. `GET /api/sheet`
- **Output**: Proxies the Google Sheet CSV data securely using Render environment variable `SHEET_CSV_URL`.
- **Privacy**: The raw Google Sheet URL is completely hidden from the client-side frontend.

---

## 4. Frontend UI Features (`preview.html`)

- **Default Initial View**: Daily Timeline View opens first with period 1–6 cards, topics, and status badges.
- **Controls Layout**:
  - **Left**: `[ Daily Timeline ]` | `[ Matrix View ]` switcher buttons.
  - **Right**: `MONTH:` and `SUBJECT:` dropdown filters.
- **Cell Drilldown Modal**: Click on any period card or matrix cell to view period numbers, topic taught, status, and direct buttons for PowerPoint slides & YouTube lectures.
- **Timetable Matrix**: Clean Monday–Saturday rows $\times$ Period 1–6 (+ Lunch Break) columns, room pins, faculty names, and full 11-course directory.
- **Share & Privacy Modal**:
  - Privacy options: Friends Only (IARE Lake ecosystem), Public (link access), Private (disabled).
  - Granular checkboxes: Register, Topics, Timetable, Hide Contacts.
  - Token Link Generator with 1-click copy.
  - Auto-detects `?token=...` for read-only shared view.

---

## 5. Deployment & Running

### Local Development:
```bash
python app.py
```
Open browser at: `http://127.0.0.1:10000/preview`

### Production on Render:
- **Build Command**: `pip install -r requirements.txt` (or Docker build)
- **Start Command**: `gunicorn -b 0.0.0.0:10000 app:app --timeout 30 --workers 2`
- **Environment Variables**:
  - `SHEET_CSV_URL`: The published Google Sheets CSV URL.
