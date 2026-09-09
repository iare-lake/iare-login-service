import os
import re
import uuid
import requests
from bs4 import BeautifulSoup
# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "service": "IARE LAKE Backend"}), 200

# In-memory store for shared tokens (can also sync with Firebase / DB)
SHARED_TOKENS = {}

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Referer": "https://samvidha.iare.ac.in/index.php"
}

def do_fast_login(roll, password):
    """Logs in via the hidden AJAX API with dynamic CSRF handling. Returns session if successful, else None."""
    session = requests.Session()
    try:
        r = session.get("https://samvidha.iare.ac.in/index.php", headers=BASE_HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        meta = soup.find('meta', {'name': 'csrf-token'})
        csrf = meta.get('content') if meta else ''
        
        ajax_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": csrf,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://samvidha.iare.ac.in/index.php"
        }
        login_url = "https://samvidha.iare.ac.in/pages/login/checkUser.php"
        payload = {"username": roll, "password": password}
        resp = session.post(login_url, data=payload, headers=ajax_headers, timeout=10)
        
        if resp.status_code == 200 and resp.json().get("status") == "1":
            return session
            
        resp_fallback = session.post(login_url, data=payload, headers=BASE_HEADERS, timeout=10)
        if resp_fallback.status_code == 200 and resp_fallback.json().get("status") == "1":
            return session
            
    except Exception as e:
        print(f"Login Error: {e}")
    return None

def get_home_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Referer": "https://samvidha.iare.ac.in/home"
    }

def scrape_profile_data(session):
    """Scrapes student profile details from https://samvidha.iare.ac.in/home?action=profile"""
    try:
        prof_url = "https://samvidha.iare.ac.in/home?action=profile"
        resp = session.get(prof_url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        profile_data = {}

        def match_and_set(label, val):
            if not val or val.strip() in ["", "--", "N/A", "null", "None"]:
                return
            l = label.lower().strip()
            v = val.strip()
            if not v or l.isdigit() or l in ["s.no", "view", "status"]:
                return
            if ("aebas" in l or "jntuh" in l) and "jntuhAebas" not in profile_data:
                profile_data["jntuhAebas"] = v
            elif ("abc" in l and "id" in l) and "abcId" not in profile_data:
                profile_data["abcId"] = v
            elif ("gender" in l or "sex" in l) and "gender" not in profile_data:
                profile_data["gender"] = v
            elif ("date of birth" in l or "birth" in l or "dob" in l) and "dob" not in profile_data:
                profile_data["dob"] = v
            elif ("date of joining" in l or "joining" in l or "doj" in l) and "doj" not in profile_data:
                profile_data["doj"] = v
            elif ("caste" in l or "category" in l or "community" in l) and "fee" not in l and "casteCategory" not in profile_data:
                profile_data["casteCategory"] = v
                profile_data["caste"] = v
            elif ("student phone" in l or "student mobile" in l) and "mobile" not in profile_data:
                profile_data["mobile"] = v
            elif ("parent phone" in l or "parent mobile" in l) and "parentPhone" not in profile_data:
                profile_data["parentPhone"] = v
            elif ("mobile" in l or "phone" in l or "cell" in l) and "mobile" not in profile_data:
                profile_data["mobile"] = v
            elif ("student email" in l or "student mail" in l) and "mail" not in profile_data:
                profile_data["mail"] = v
            elif ("parent email" in l or "parent mail" in l) and "parentEmail" not in profile_data:
                profile_data["parentEmail"] = v
            elif ("domain email" in l) and "domainEmail" not in profile_data:
                profile_data["domainEmail"] = v
            elif ("email" in l or "mail" in l) and "mail" not in profile_data:
                profile_data["mail"] = v
            elif "section" in l and "section" not in profile_data:
                profile_data["section"] = v
            elif ("branch" in l or "dept" in l) and "branch" not in profile_data:
                profile_data["branch"] = v
            elif ("year" in l or "sem" in l) and "year" not in profile_data and "b.tech" not in l.replace(" ", ""):
                profile_data["year"] = v
            elif "roll" in l and "number" in l and "roll" not in profile_data:
                profile_data["roll"] = v
            elif "regulation" in l and "regulation" not in profile_data:
                profile_data["regulation"] = v
            elif "father" in l and "name" in l and "fatherName" not in profile_data:
                profile_data["fatherName"] = v
            elif "mother" in l and "name" in l and "motherName" not in profile_data:
                profile_data["motherName"] = v
            elif "religion" in l and "religion" not in profile_data:
                profile_data["religion"] = v
            elif ("name" in l) and "name" not in profile_data and "course" not in l and "father" not in l and "mother" not in l:
                profile_data["name"] = v

        for dl in soup.find_all('dl'):
            for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                match_and_set(dt.get_text(strip=True), dd.get_text(strip=True))

        for strong in soup.find_all('strong'):
            next_p = strong.find_next_sibling('p')
            if next_p:
                match_and_set(strong.get_text(strip=True), next_p.get_text(strip=True))

        for row in soup.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                for i in range(0, len(cols) - 1, 2):
                    match_and_set(cols[i].text.strip(), cols[i+1].text.strip())

        # Scrape SGPA & CGPA from Credit Register
        try:
            credit_info = scrape_credit_register(session)
            if credit_info.get("success"):
                profile_data["academic"] = {
                    "sgpaList": credit_info.get("sgpaList", []),
                    "cgpa": credit_info.get("cgpa")
                }
                if credit_info.get("cgpa"):
                    profile_data["cgpa"] = credit_info.get("cgpa")
        except Exception as e_cr:
            print(f"Credit Register attached error: {e_cr}")

        return profile_data
    except Exception as e:
        print(f"Profile Scraping Error: {e}")
        return {}

def extract_registered_courses(session):
    """Fetches course content page and returns list of all registered course dicts."""
    courses = []
    try:
        cc_url = "https://samvidha.iare.ac.in/home?action=course_content"
        resp = session.get(cc_url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table')
        if table:
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                if len(cells) == 1 or (cells[0].get('colspan') and int(cells[0].get('colspan', 1)) >= 5):
                    text = cells[0].text.strip()
                    if " - " in text and not text.lower().startswith("academic year") and not text.lower().startswith("s.no"):
                        parts = text.split(" - ", 1)
                        code = parts[0].strip()
                        name = parts[1].strip() if len(parts) > 1 else code
                        is_lab = "lab" in name.lower() or "laboratory" in name.lower() or code.endswith("L")
                        if not any(c["code"] == code for c in courses):
                            courses.append({
                                "code": code,
                                "name": name,
                                "fullName": text,
                                "isLab": is_lab
                            })
    except Exception as e:
        print(f"Error fetching registered courses: {e}")
    return courses

COMMON_SUBJECT_ALIASES = {
    "Object Oriented Programming Systems": "OOPS",
    "Object Oriented Programming": "OOP",
    "Data Handling and Visualization Techniques": "DHVT",
    "Data Handling and Visualization Techniques Laboratory": "DHVTL",
    "Design and Analysis of Algorithms": "DAA",
    "Design and Analysis of Algorithms Laboratory": "DAAL",
    "Database Management Systems": "DBMS",
    "Database Management Systems Laboratory": "DBMSL",
    "Mobile Applications Development Laboratory": "MADL",
    "Mobile Applications Development": "MAD",
    "Probability and Statistics Methods": "PSM",
    "Computer System and Architecture": "CSA",
    "Computer System & Architecture": "CSA",
    "Computer Organization and Architecture": "COA",
    "Programming with Objects": "PWO",
    "Intelligent Systems": "IS",
    "Intelligent Systems Laboratory": "ISL",
    "Environmental and Sustainable Development": "ESD",
    "English for Skill Enhancement": "ESE",
    "English for Skill Enhancement Laboratory": "ESEL",
    "Full Stack Development": "FSD",
    "Full Stack Development Laboratory": "FSDL",
    "Operating Systems": "OS",
    "Operating Systems Laboratory": "OSL",
    "Computer Networks": "CN",
    "Computer Networks Laboratory": "CNL",
    "Software Engineering": "SE",
    "Artificial Intelligence": "AI",
    "Machine Learning": "ML",
    "Data Structures": "DS",
    "Data Structures Laboratory": "DSL"
}

def get_subject_short_name(name, code=""):
    if not name:
        return code
    cleaned = re.sub(r'\(.*?\)', '', name).strip()
    # Check known dictionary first
    if cleaned in COMMON_SUBJECT_ALIASES:
        return COMMON_SUBJECT_ALIASES[cleaned]
    for k, v in COMMON_SUBJECT_ALIASES.items():
        if k.lower() == cleaned.lower():
            return v
            
    # Universal Dynamic Acronym Generator for ANY present or future subject
    is_lab = "lab" in cleaned.lower() or "laboratory" in cleaned.lower() or (code and code.endswith("L"))
    stop_words = {'and', 'of', 'for', 'in', 'the', 'with', '&', 'to', 'on', 'at', 'by', 'an', 'a'}
    words = [w for w in re.split(r'[\s\-]+', cleaned) if w and w.lower() not in stop_words]
    
    letters = []
    for w in words:
        if w.lower() in ['laboratory', 'lab']:
            letters.append('L')
        else:
            first_char = w[0].upper()
            if first_char.isalnum():
                letters.append(first_char)
                
    acronym = "".join(letters)
    if is_lab and not acronym.endswith('L'):
        acronym += 'L'
        
    return acronym if acronym else code

def scrape_credit_register(session):
    """Scrapes Semester SGPA breakdown and overall CGPA from Credit Register."""
    try:
        url = "https://samvidha.iare.ac.in/home?action=credit_register"
        resp = session.get(url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        sgpa_list = []
        overall_cgpa = None
        current_sem = None
        
        for tr in soup.find_all('tr'):
            text = tr.text.strip()
            # Find semester headers e.g. "I SEMESTER", "II SEMESTER", "III SEMESTER"
            sem_m = re.search(r'([IVXLCDM]+)\s*SEMESTER', text, re.I)
            if sem_m:
                roman = sem_m.group(1).upper()
                roman_map = {
                    "I": "Semester 1", "II": "Semester 2", "III": "Semester 3",
                    "IV": "Semester 4", "V": "Semester 5", "VI": "Semester 6",
                    "VII": "Semester 7", "VIII": "Semester 8"
                }
                current_sem = roman_map.get(roman, f"Semester {roman}")
            
            # Find SGPA
            if "Semester Grade Point Average" in text or "SGPA" in text:
                sgpa_m = re.search(r'SGPA\s*\)\s*:\s*([0-9\.]+)', text, re.I)
                if sgpa_m and current_sem:
                    sgpa_val = sgpa_m.group(1).strip()
                    if not any(s["semester"] == current_sem for s in sgpa_list):
                        sgpa_list.append({
                            "semester": current_sem,
                            "sgpa": sgpa_val
                        })
            
            # Find CGPA
            if "Cumulative Grade Point Average" in text or "CGPA" in text:
                cgpa_m = re.search(r'CGPA\s*\)\s*:\s*([0-9\.]+)', text, re.I)
                if cgpa_m:
                    overall_cgpa = cgpa_m.group(1).strip()
        
        return {
            "success": True,
            "sgpaList": sgpa_list,
            "cgpa": overall_cgpa
        }
    except Exception as e:
        print(f"Credit Register Scraping Error: {e}")
        return {"success": False, "error": str(e), "sgpaList": [], "cgpa": None}

def scrape_attendance_register_data(session):
    """Scrapes Course Content Delivery and compiles a complete Date x Subject Attendance Register."""
    try:
        cc_url = "https://samvidha.iare.ac.in/home?action=course_content"
        resp = session.get(cc_url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table')
        if not table:
            return {"error": "Course content table not found"}
        
        ay_match = re.search(r'Academic\s*Year\s*:\s*([0-9\-]+)', table.text, re.I)
        academic_year = ay_match.group(1) if ay_match else ""
        
        courses = []
        current_course = None
        all_lectures = []
        
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if not cells:
                continue
            
            if len(cells) == 1 or (cells[0].get('colspan') and int(cells[0].get('colspan', 1)) >= 5):
                text = cells[0].text.strip()
                if " - " in text and not text.lower().startswith("academic year") and not text.lower().startswith("s.no"):
                    parts = text.split(" - ", 1)
                    code = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else code
                    is_lab = "lab" in name.lower() or "laboratory" in name.lower() or code.endswith("L")
                    short_name = get_subject_short_name(name, code)
                    display_code = f"{code} - {short_name}" if short_name and short_name != code else code
                    current_course = {
                        "code": code,
                        "name": name,
                        "shortName": short_name,
                        "displayCode": display_code,
                        "fullName": text,
                        "isLab": is_lab
                    }
                    if not any(c["code"] == code for c in courses):
                        courses.append(current_course)
                continue
            
            if len(cells) >= 5 and current_course:
                sno_text = cells[0].text.strip()
                if not sno_text.isdigit():
                    continue
                
                date_raw = cells[1].text.strip()
                period_raw = cells[2].text.strip()
                topic = cells[3].text.strip()
                status = cells[4].text.strip().upper()
                
                yt_link = None
                if len(cells) >= 6:
                    yt_a = cells[5].find('a')
                    if yt_a and yt_a.get('href'):
                        yt_link = yt_a.get('href').strip()
                    elif cells[5].text.strip() and cells[5].text.strip().lower() != 'nil':
                        yt_link = cells[5].text.strip()
                
                ppt_link = None
                if len(cells) >= 7:
                    ppt_a = cells[6].find('a')
                    if ppt_a and ppt_a.get('href'):
                        ppt_link = ppt_a.get('href').strip()
                
                iso_date = ""
                date_obj = None
                try:
                    date_clean = re.sub(r'[\xa0\s]+', ' ', date_raw)
                    date_obj = datetime.strptime(date_clean, "%d %b, %Y")
                    iso_date = date_obj.strftime("%Y-%m-%d")
                except Exception:
                    try:
                        date_obj = datetime.strptime(date_raw, "%d-%b-%Y")
                        iso_date = date_obj.strftime("%Y-%m-%d")
                    except Exception:
                        iso_date = date_raw
                
                period_num = int(period_raw) if period_raw.isdigit() else period_raw
                
                lecture = {
                    "courseCode": current_course["code"],
                    "courseName": current_course["name"],
                    "shortName": current_course.get("shortName", ""),
                    "displayCode": current_course.get("displayCode", current_course["code"]),
                    "fullName": current_course.get("fullName", f"{current_course['code']} - {current_course['name']}"),
                    "isLab": current_course.get("isLab", False),
                    "date": iso_date,
                    "dateDisplay": date_raw,
                    "dateObj": date_obj,
                    "period": period_num,
                    "topic": topic,
                    "status": status,
                    "youtubeLink": yt_link,
                    "pptLink": ppt_link
                }
                all_lectures.append(lecture)
        
        dates_map = {}
        for lec in all_lectures:
            d_key = lec["date"]
            if d_key not in dates_map:
                month_str = lec["dateObj"].strftime("%b %Y") if lec["dateObj"] else "Unknown"
                dates_map[d_key] = {
                    "date": d_key,
                    "dateDisplay": lec["dateDisplay"],
                    "dateObj": lec["dateObj"],
                    "month": month_str,
                    "lectures": [],
                    "subjectsMap": {},
                    "periodsTimeline": {str(p): None for p in range(1, 8)}
                }
            
            dates_map[d_key]["lectures"].append(lec)
            c_code = lec["courseCode"]
            if c_code not in dates_map[d_key]["subjectsMap"]:
                dates_map[d_key]["subjectsMap"][c_code] = {
                    "courseCode": c_code,
                    "courseName": lec["courseName"],
                    "shortName": lec.get("shortName", ""),
                    "displayCode": lec.get("displayCode", c_code),
                    "fullName": lec.get("fullName", f"{c_code} - {lec['courseName']}"),
                    "isLab": lec.get("isLab", False),
                    "periods": [],
                    "presentCount": 0,
                    "absentCount": 0,
                    "totalCount": 0
                }
            
            s_entry = dates_map[d_key]["subjectsMap"][c_code]
            s_entry["periods"].append({
                "period": lec["period"],
                "status": lec["status"],
                "topic": lec["topic"],
                "youtubeLink": lec["youtubeLink"],
                "pptLink": lec["pptLink"]
            })
            s_entry["totalCount"] += 1
            if "PRESENT" in lec["status"]:
                s_entry["presentCount"] += 1
            elif "ABSENT" in lec["status"]:
                s_entry["absentCount"] += 1
                
            p_str = str(lec["period"])
            dates_map[d_key]["periodsTimeline"][p_str] = {
                "courseCode": c_code,
                "courseName": lec["courseName"],
                "shortName": lec.get("shortName", ""),
                "displayCode": lec.get("displayCode", c_code),
                "fullName": lec.get("fullName", f"{c_code} - {lec['courseName']}"),
                "isLab": lec.get("isLab", False),
                "period": lec["period"],
                "status": lec["status"],
                "topic": lec["topic"],
                "youtubeLink": lec["youtubeLink"],
                "pptLink": lec["pptLink"]
            }
        
        formatted_dates = []
        available_months_set = []
        sorted_date_keys = sorted(dates_map.keys(), key=lambda d: dates_map[d]["dateObj"] or datetime.min, reverse=True)
        
        for d_key in sorted_date_keys:
            d_val = dates_map[d_key]
            month_name = d_val["month"]
            if month_name not in available_months_set and month_name != "Unknown":
                available_months_set.append(month_name)
            
            day_present = sum(s["presentCount"] for s in d_val["subjectsMap"].values())
            day_absent = sum(s["absentCount"] for s in d_val["subjectsMap"].values())
            day_total = sum(s["totalCount"] for s in d_val["subjectsMap"].values())
            day_pct = f"{(day_present / day_total * 100):.1f}%" if day_total > 0 else "0.0%"
            
            records = {}
            for c_code, s_info in d_val["subjectsMap"].items():
                pres = s_info["presentCount"]
                ab = s_info["absentCount"]
                
                if pres > 0 and ab == 0:
                    display = f"P ({pres})" if pres > 1 else "P"
                elif ab > 0 and pres == 0:
                    display = f"A ({ab})" if ab > 1 else "A"
                elif pres > 0 and ab > 0:
                    display = f"P ({pres}), A ({ab})"
                else:
                    display = "—"
                
                s_info["display"] = display
                s_info["periods"] = sorted(s_info["periods"], key=lambda x: x["period"] if isinstance(x["period"], int) else 99)
                records[c_code] = s_info
            
            formatted_dates.append({
                "date": d_key,
                "dateDisplay": d_val["dateDisplay"],
                "month": month_name,
                "daySummary": {
                    "totalConducted": day_total,
                    "totalPresent": day_present,
                    "totalAbsent": day_absent,
                    "percentage": day_pct
                },
                "records": records,
                "periodsTimeline": d_val["periodsTimeline"]
            })
        
        subject_stats = []
        for c in courses:
            code = c["code"]
            c_pres = sum(d["records"][code]["presentCount"] for d in formatted_dates if code in d["records"])
            c_abs = sum(d["records"][code]["absentCount"] for d in formatted_dates if code in d["records"])
            c_tot = sum(d["records"][code]["totalCount"] for d in formatted_dates if code in d["records"])
            c_pct = f"{(c_pres / c_tot * 100):.1f}%" if c_tot > 0 else "0.0%"
            
            subject_stats.append({
                "code": code,
                "name": c["name"],
                "shortName": c.get("shortName", ""),
                "displayCode": c.get("displayCode", code),
                "fullName": c["fullName"],
                "isLab": c.get("isLab", False),
                "totalHeld": c_tot,
                "totalPresent": c_pres,
                "totalAbsent": c_abs,
                "percentage": c_pct
            })
            
        overall_total = sum(s["totalHeld"] for s in subject_stats)
        overall_present = sum(s["totalPresent"] for s in subject_stats)
        overall_absent = sum(s["totalAbsent"] for s in subject_stats)
        overall_pct = f"{(overall_present / overall_total * 100):.1f}%" if overall_total > 0 else "0.0%"
        
        return {
            "academicYear": academic_year,
            "subjects": subject_stats,
            "availableMonths": available_months_set,
            "summary": {
                "totalConducted": overall_total,
                "totalPresent": overall_present,
                "totalAbsent": overall_absent,
                "overallPercentage": overall_pct
            },
            "dates": formatted_dates
        }
    except Exception as e:
        print(f"Attendance Register Scraping Error: {e}")
        return {"error": str(e)}

def scrape_timetable_data(session):
    """Scrapes official Student Timetable from https://samvidha.iare.ac.in/home?action=TT_std with complete course and faculty mapping."""
    try:
        reg_courses = extract_registered_courses(session)
        
        tt_url = "https://samvidha.iare.ac.in/home?action=TT_std"
        resp_get = session.get(tt_url, headers=get_home_headers(), timeout=15)
        soup_get = BeautifulSoup(resp_get.text, 'html.parser')
        
        ay_select = soup_get.find('select', {'id': 'ay'}) or soup_get.find('select', {'name': 'ay'})
        sec_select = soup_get.find('select', {'id': 'sec_data'}) or soup_get.find('select', {'name': 'sec_data'})
        
        ay_val = ""
        if ay_select:
            first_opt = ay_select.find('option')
            if first_opt:
                ay_val = first_opt.get('value', '').strip()
                
        sec_val = ""
        if sec_select:
            for opt in sec_select.find_all('option'):
                v = opt.get('value', '').strip()
                if v:
                    sec_val = v
                    break
        
        payload = {
            "ay": ay_val,
            "sec_data": sec_val,
            "btn_faculty_tt": "show"
        }
        resp_post = session.post(tt_url, data=payload, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp_post.text, 'html.parser')
        tables = soup.find_all('table')
        if not tables:
            tables = soup_get.find_all('table')
        if not tables:
            return {"error": "Timetable tables not found"}
        
        grid_table = tables[0]
        dir_table = tables[1] if len(tables) > 1 else None
        timings_table = tables[2] if len(tables) > 2 else None
        
        subjects_dir = {}
        faculty_id_name_map = {}
        
        if dir_table:
            for r in dir_table.find_all('tr'):
                tds = [c.text.strip() for c in r.find_all(['td', 'th'])]
                if len(tds) >= 6 and tds[0].isdigit():
                    short_code = tds[3].strip()
                    sub_code = tds[1].strip()
                    sub_name = tds[2].strip()
                    staff_id = tds[4].strip()
                    staff_name = tds[5].strip()
                    is_lab = "lab" in sub_name.lower() or "laboratory" in sub_name.lower() or sub_code.endswith("L")
                    
                    subjects_dir[short_code] = {
                        "subjectCode": sub_code,
                        "subjectName": sub_name,
                        "shortCode": short_code,
                        "staffId": staff_id,
                        "staffName": staff_name,
                        "isLab": is_lab
                    }
                    faculty_id_name_map[staff_id] = staff_name
        
        def make_shortcode(code, name):
            aliases = {
                "Data Handling and Visualization Techniques": "DHVT",
                "Data Handling and Visualization Techniques Laboratory": "DHVTL",
                "Design and Analysis of Algorithms": "DAA",
                "Design and Analysis of Algorithms Laboratory": "DAAL",
                "Mobile Applications Development Laboratory": "MADL",
                "Probability and Statistics Methods": "PSM",
                "Computer System and Architecture": "CSA",
                "Database Management Systems": "DBMS",
                "Database Management Systems Laboratory": "DBMSL",
                "Programming with Objects": "PWO",
                "Intelligent Systems": "IS",
                "Intelligent Systems Laboratory": "ISL",
                "Environmental and Sustainable Development": "ESD"
            }
            if name in aliases:
                return aliases[name]
            words = [w for w in re.split(r'[\s\-]+', name) if w and w.lower() not in ['and', 'of', 'with', '&', 'the', 'in']]
            return "".join(w[0].upper() for w in words)
        
        for c in reg_courses:
            code = c["code"]
            name = c["name"]
            is_lab = c.get("isLab", False)
            short = make_shortcode(code, name)
            
            if short not in subjects_dir:
                existing = next((s for s in subjects_dir.values() if s["subjectCode"] == code), None)
                if not existing:
                    subjects_dir[short] = {
                        "subjectCode": code,
                        "subjectName": name,
                        "shortCode": short,
                        "staffId": "",
                        "staffName": "Department Faculty",
                        "isLab": is_lab
                    }
                else:
                    existing["isLab"] = is_lab
            else:
                subjects_dir[short]["subjectCode"] = code
                subjects_dir[short]["subjectName"] = name
                subjects_dir[short]["isLab"] = is_lab
        
        bell_timings = [
            {"period": 1, "label": "Period - I", "time": "09:30 AM - 10:25 AM"},
            {"period": 2, "label": "Period - II", "time": "10:25 AM - 11:20 AM"},
            {"period": 3, "label": "Period - III", "time": "11:20 AM - 12:15 PM"},
            {"period": "LUNCH", "label": "Lunch Break", "time": "12:15 PM - 01:05 PM"},
            {"period": 4, "label": "Period - IV", "time": "01:05 PM - 02:00 PM"},
            {"period": 5, "label": "Period - V", "time": "02:00 PM - 02:55 PM"},
            {"period": 6, "label": "Period - VI", "time": "02:55 PM - 03:50 PM"}
        ]
        
        academic_year_found = ay_val
        branch_found = sec_val
        weekly_schedule = {}
        period_headers = ["Period - I", "Period - II", "Period - III", "Period - IV", "Period - V", "Period - VI"]
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        for row in grid_table.find_all('tr'):
            tds = row.find_all(['td', 'th'])
            if not tds:
                continue
            
            row_text = row.text
            if "Academic Year" in row_text:
                m = re.search(r'Academic Year\s*([0-9\-]+)', row_text)
                if m:
                    academic_year_found = m.group(1).strip()
                m_br = re.search(r'Branch/Section\s*([^\n\r]+)', row_text)
                if m_br:
                    raw_br = m_br.group(1).strip()
                    # Clean internal Samvidha ID prefix like 348: or 340:
                    branch_found = re.sub(r'^\d+:\s*', '', raw_br).strip()
                continue
                
            if "DAY/PERIOD" in row_text:
                period_headers = [c.text.strip() for c in tds[1:] if c.text.strip()]
                continue
                
            day_cell = tds[0]
            day_text = day_cell.text.strip()
            day_name = re.split(r'[\d\-]', day_text)[0].strip()
            date_sub = day_text.replace(day_name, "").strip()
            
            if not day_name or day_name not in days_order:
                continue
                
            day_periods = []
            for p_idx, col in enumerate(tds[1:]):
                cell_text = col.text.strip()
                
                room_m = re.search(r'Room\s*:\s*([A-Za-z0-9\-\s\/]+?)(?=(?:Faculty\s*Id|$))', cell_text, re.I)
                room_val = room_m.group(1).strip() if room_m else ""
                
                fac_m = re.search(r'Faculty\s*Id\s*:\s*([^<\n\r]+)', cell_text, re.I)
                fac_val = fac_m.group(1).strip() if fac_m else ""
                
                short_code_m = re.search(r'^([A-Za-z0-9\/]+)', cell_text)
                raw_short = short_code_m.group(1).strip() if short_code_m else cell_text.split(" ")[0].strip()
                primary_short = raw_short.split('/')[0].strip()
                
                matched_subject = subjects_dir.get(primary_short, {})
                
                all_fids = [f.strip() for f in fac_val.split('/') if f.strip()]
                resolved_names = [faculty_id_name_map[fid] for fid in all_fids if fid in faculty_id_name_map]
                if not resolved_names and all_fids:
                    resolved_names = [f"Staff ({fid})" for fid in all_fids]

                faculty_name = matched_subject.get("staffName", "")
                if resolved_names:
                    primary_faculty = resolved_names[0]
                    all_faculties_str = " / ".join(resolved_names)
                else:
                    primary_faculty = faculty_name or "Department Faculty"
                    all_faculties_str = faculty_name or "Department Faculty"
                
                p_num = p_idx + 1
                t_obj = next((b for b in bell_timings if b["period"] == p_num), None)
                timing_str = t_obj["time"] if t_obj else ""
                is_lab = matched_subject.get("isLab", False) or "L" in primary_short or "lab" in matched_subject.get("subjectName", "").lower()
                
                day_periods.append({
                    "period": p_num,
                    "periodLabel": f"Period - {p_num}",
                    "timing": timing_str,
                    "shortCode": primary_short,
                    "rawShortCode": raw_short,
                    "subjectCode": matched_subject.get("subjectCode", ""),
                    "subjectName": matched_subject.get("subjectName", primary_short),
                    "isLab": is_lab,
                    "room": room_val,
                    "facultyId": fac_val,
                    "facultyName": primary_faculty,
                    "allFaculties": all_faculties_str
                })
                
            weekly_schedule[day_name] = {
                "day": day_name,
                "date": date_sub,
                "periods": day_periods
            }
            
        final_directory = sorted(list(subjects_dir.values()), key=lambda x: (x.get("isLab", False), x.get("shortCode", "")))
        
        return {
            "academicYear": academic_year_found,
            "branchSection": branch_found,
            "bellTimings": bell_timings,
            "subjectsDirectory": final_directory,
            "schedule": weekly_schedule
        }
    except Exception as e:
        print(f"Timetable Scraping Error: {e}")
        return {"error": str(e)}

# --- ROUTES ---

@app.route('/api/verify', methods=['POST'])
def verify_user():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"valid": False, "error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if session:
        prof_data = scrape_profile_data(session)
        return jsonify({"valid": True, "profile": prof_data, "samvidha": prof_data})
    return jsonify({"valid": False, "error": "Invalid credentials"})

@app.route('/api/profile', methods=['POST'])
def get_profile():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        prof_data = scrape_profile_data(session)
        return jsonify({"success": True, "data": prof_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/attendance', methods=['POST'])
def get_attendance():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        att_url = "https://samvidha.iare.ac.in/home?action=stud_att_STD"
        resp = session.get(att_url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        target_table = None
        for t in soup.find_all('table'):
            if "Course Name" in t.text:
                target_table = t
                break
        if not target_table:
            return jsonify({"error": "Attendance table not found"}), 404
        rows = target_table.find_all('tr')
        attendance_data = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) >= 8:
                attendance_data.append({
                    "subject": cols[2].text.strip(),
                    "total": cols[5].text.strip(),
                    "present": cols[6].text.strip(),
                    "percent": cols[7].text.strip()
                })
        return jsonify({"success": True, "data": attendance_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/attendance-register', methods=['POST'])
def get_attendance_register():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    res = scrape_attendance_register_data(session)
    if "error" in res:
        return jsonify({"error": res["error"]}), 500
    return jsonify({"success": True, "data": res})

@app.route('/api/timetable', methods=['POST'])
def get_timetable():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    res = scrape_timetable_data(session)
    if "error" in res:
        return jsonify({"error": res["error"]}), 500
    return jsonify({"success": True, "data": res})

# --- SHARE & PRIVACY API ---

@app.route('/api/share/create', methods=['POST'])
def create_share_token():
    """Generates a share token snapshot with privacy level and options."""
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    privacy_mode = data.get('privacy', 'friends') # 'public', 'friends', 'private'
    permissions = data.get('permissions', {
        "shareRegister": True,
        "shareTimetable": True,
        "shareTopics": True,
        "hideContact": True
    })

    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400

    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    prof_data = scrape_profile_data(session)
    reg_data = scrape_attendance_register_data(session) if permissions.get("shareRegister", True) else None
    tt_data = scrape_timetable_data(session) if permissions.get("shareTimetable", True) else None

    # Generate Short Token
    token_id = "iare_" + uuid.uuid4().hex[:8]

    student_name = prof_data.get("name", roll)
    if permissions.get("hideContact", True):
        prof_data.pop("mobile", None)
        prof_data.pop("parentPhone", None)
        prof_data.pop("mail", None)
        prof_data.pop("parentEmail", None)

    SHARED_TOKENS[token_id] = {
        "token": token_id,
        "roll": roll,
        "studentName": student_name,
        "branch": prof_data.get("branch", ""),
        "section": prof_data.get("section", ""),
        "privacy": privacy_mode,
        "permissions": permissions,
        "createdAt": datetime.now().isoformat(),
        "register": reg_data,
        "timetable": tt_data
    }

    return jsonify({
        "success": True,
        "token": token_id,
        "privacy": privacy_mode,
        "shareUrl": f"/preview?token={token_id}",
        "studentName": student_name
    })

@app.route('/api/share/<token_id>', methods=['GET'])
def get_shared_data(token_id):
    """Retrieves shared attendance and timetable by token ID (read-only, no password required)."""
    if token_id not in SHARED_TOKENS:
        return jsonify({"error": "Share token not found or expired"}), 404

    shared_entry = SHARED_TOKENS[token_id]
    if shared_entry.get("privacy") == "private":
        return jsonify({"error": "Sharing has been set to Private by student"}), 403

    return jsonify({
        "success": True,
        "data": {
            "token": shared_entry["token"],
            "roll": shared_entry["roll"],
            "studentName": shared_entry["studentName"],
            "branch": shared_entry.get("branch", ""),
            "section": shared_entry.get("section", ""),
            "privacy": shared_entry.get("privacy", "friends"),
            "permissions": shared_entry.get("permissions", {}),
            "createdAt": shared_entry.get("createdAt"),
            "register": shared_entry.get("register"),
            "timetable": shared_entry.get("timetable")
        }
    })

@app.route('/api/biometric', methods=['POST'])
def get_biometric():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        bio_url = "https://samvidha.iare.ac.in/home?action=std_bio"
        resp = session.get(bio_url, headers=get_home_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        target_table = None
        for t in soup.find_all('table'):
            if "In Time" in t.text and "Status" in t.text:
                target_table = t
                break
        if not target_table:
            return jsonify({"error": "Biometric table not found"}), 404
        rows = target_table.find_all('tr')
        biometric_data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 7:
                date_str = cols[3].text.strip()
                status = cols[9].text.strip() if len(cols) >= 10 else ""
                if date_str and "Date" not in date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%d-%b-%Y")
                        iso_date = date_obj.strftime("%Y-%m-%d")
                        biometric_data.append({
                            "date": iso_date,
                            "status": status
                        })
                    except ValueError:
                        continue
        if not biometric_data:
            return jsonify({"error": "Biometric records empty"}), 404
        return jsonify({"success": True, "data": biometric_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/credit-register', methods=['POST'])
def get_credit_register():
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    res = scrape_credit_register(session)
    return jsonify(res)

@app.route('/api/download', methods=['POST'])
def proxy_download():
    data = request.json or {}
    roll = data.get('roll')
    doc_type = data.get('type')
    base_url = "https://iare-data.s3.ap-south-1.amazonaws.com/uploads"
    if doc_type == "PHOTO":
        s3_url = f"{base_url}/STUDENTS/{roll}/{roll}.jpg"
        filename = f"{roll}.jpg"
        content_type = "image/jpeg"
    elif doc_type == "FIELDPROJECT":
        s3_url = f"{base_url}/FIELDPROJECT/2024-25_{roll}_FM.pdf"
        filename = f"{roll}_FieldProject.pdf"
        content_type = "application/pdf"
    else:
        s3_url = f"{base_url}/STUDENTS/{roll}/DOCS/{roll}_{doc_type}.jpg"
        filename = f"{roll}_{doc_type}.jpg"
        content_type = "image/jpeg"
    try:
        remote = requests.get(s3_url, stream=True)
        if remote.status_code != 200:
            return jsonify({"error": "File not found"}), 404
        headers = { "Content-Disposition": f"attachment; filename={filename}", "Content-Type": content_type }
        return Response(remote.iter_content(chunk_size=1024), headers=headers, status=200)
    except:
        return jsonify({"error": "Server Error"}), 500

@app.route('/api/check_worksheet', methods=['POST', 'GET'])
def check_worksheet():
    """Checks if an S3 worksheet PDF actually exists without exposing AccessDenied XML to user."""
    data = request.json if request.is_json else request.args
    url = data.get("url") if data else None
    if not url:
        return jsonify({"success": False, "exists": False, "error": "Missing URL"}), 400
    try:
        r = requests.head(url, timeout=5)
        if r.status_code == 200:
            return jsonify({"success": True, "exists": True, "url": url})
        return jsonify({"success": True, "exists": False, "url": url, "status_code": r.status_code})
    except Exception as e:
        return jsonify({"success": False, "exists": False, "error": str(e)}), 500

@app.route('/api/sheet', methods=['GET'])
def proxy_sheet():
    """Proxies Google Sheet CSV data securely using Render environment variable SHEET_CSV_URL."""
    sheet_url = os.environ.get("SHEET_CSV_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vShhU-9jmKqFELdaUJaZBkkpz7U-BiRVzzViGZ3VPRQh__6bj6V171tzgeZRK32cxMLPEGx8tBxzRfW/pub?output=csv")
    if not sheet_url:
        return jsonify({"error": "SHEET_CSV_URL not configured"}), 500
    try:
        resp = requests.get(sheet_url, timeout=12)
        if resp.status_code != 200:
            return jsonify({"error": f"Failed to fetch sheet (status {resp.status_code})"}), 502
        headers = {
            "Content-Type": "text/csv; charset=utf-8",
            "Cache-Control": "public, max-age=300"
        }
        return Response(resp.text, headers=headers, status=200)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return send_from_directory('.', 'preview.html')

@app.route('/preview')
def preview():
    return send_from_directory('.', 'preview.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
