import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Standard Browser Headers for scraping pages
GET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://samvidha.iare.ac.in/home"
}

# AJAX Headers for Login POST
POST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://samvidha.iare.ac.in/index.php"
}

def do_fast_login(roll, password):
    """Logs in via the Samvidha AJAX API with robust status and cookie handling."""
    session = requests.Session()
    try:
        # Step 1: Initialize session cookies
        session.get("https://samvidha.iare.ac.in/index.php", headers=GET_HEADERS, timeout=10)
        
        # Step 2: Post login credentials with dual parameter support
        login_url = "https://samvidha.iare.ac.in/pages/login/checkUser.php"
        payload = {
            "username": roll,
            "password": password,
            "txt_uname": roll,
            "txt_pwd": password
        }
        resp = session.post(login_url, data=payload, headers=POST_HEADERS, timeout=10)
        
        # Check response status safely (handles int 1, string "1", or boolean True)
        try:
            res_json = resp.json()
            status = str(res_json.get("status", "")).strip()
            success = status in ["1", "true", "True"] or res_json.get("success") is True
        except Exception:
            # Fallback text check if response is not standard JSON
            success = '"status":1' in resp.text or '"status":"1"' in resp.text

        if success:
            # Step 3: Register logged-in state on home page
            session.get("https://samvidha.iare.ac.in/home", headers=GET_HEADERS, timeout=10)
            return session
        else:
            print(f"Login rejected by Samvidha: {resp.text}")

    except Exception as e:
        print(f"Login Exception: {e}")
        
    return None

def scrape_profile_data(session):
    """Scrapes student profile details from https://samvidha.iare.ac.in/home?action=profile"""
    try:
        prof_url = "https://samvidha.iare.ac.in/home?action=profile"
        resp = session.get(prof_url, headers=GET_HEADERS, timeout=15)
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
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
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

        for inp in soup.find_all(['input', 'select', 'textarea']):
            name_attr = (inp.get('name') or inp.get('id') or inp.get('placeholder') or '').lower()
            val = inp.get('value', '').strip()
            if val:
                match_and_set(name_attr, val)

        return profile_data
    except Exception as e:
        print(f"Profile Scraping Error: {e}")
        return {}

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
        # Step 1: Request Attendance page
        att_url = "https://samvidha.iare.ac.in/home?action=stud_att_STD"
        resp = session.get(att_url, headers=GET_HEADERS, timeout=15)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Step 2: Target the attendance table (which has "Course Code" or "ATTENDANCE REPORT")
        target_table = None
        for t in soup.find_all('table'):
            if "Course Code" in t.text or "Attended" in t.text:
                target_table = t
                break
                
        attendance_data = []
        if target_table:
            # Skip the <thead> and iterate rows
            rows = target_table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                # attendance table rows have 9 td elements
                if len(cols) >= 8:
                    attendance_data.append({
                        "code": cols[1].get_text(strip=True),
                        "subject": cols[2].get_text(strip=True),
                        "type": cols[3].get_text(strip=True),
                        "category": cols[4].get_text(strip=True),
                        "total": cols[5].get_text(strip=True),
                        "present": cols[6].get_text(strip=True),
                        "percent": cols[7].get_text(strip=True),
                        "status": cols[8].get_text(strip=True) if len(cols) > 8 else ""
                    })
        
        return jsonify({"success": True, "count": len(attendance_data), "data": attendance_data})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
        resp = session.get(bio_url, headers=GET_HEADERS, timeout=15)
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
                status = cols[9].text.strip() if len(cols) > 9 else cols[-1].text.strip()
                
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

@app.route('/api/debug-attendance', methods=['POST'])
def debug_attendance():
    """Debug route to view raw HTML length and tables found"""
    data = request.json or {}
    roll = data.get('roll')
    password = data.get('password')
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    
    att_url = "https://samvidha.iare.ac.in/home?action=stud_att_STD"
    resp = session.get(att_url, headers=GET_HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table')
    
    return jsonify({
        "html_length": len(resp.text),
        "tables_found": len(tables),
        "url_after_get": resp.url,
        "is_login_page": "txt_uname" in resp.text
    })

@app.route('/')
def home():
    return "IARE Backend Service Running ULTRA FAST"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
