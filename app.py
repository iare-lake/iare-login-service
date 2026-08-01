import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime # <-- Added this for Date Formatting

app = Flask(__name__)
CORS(app)

# The "Secret Handshake" Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://samvidha.iare.ac.in/index.php"
}

def do_fast_login(roll, password):
    """Logs in via the hidden AJAX API. Returns the session if successful, else None."""
    session = requests.Session()
    try:
        session.get("https://samvidha.iare.ac.in/index.php", headers=HEADERS, timeout=10)
        login_url = "https://samvidha.iare.ac.in/pages/login/checkUser.php"
        payload = {"username": roll, "password": password}
        resp = session.post(login_url, data=payload, headers=HEADERS, timeout=10)
        if resp.json().get("status") == "1":
            return session
    except Exception as e:
        print(f"Login Error: {e}")
    return None

def scrape_profile_data(session):
    """Scrapes student profile details from https://samvidha.iare.ac.in/home?action=profile"""
    try:
        prof_url = "https://samvidha.iare.ac.in/home?action=profile"
        resp = session.get(prof_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        profile_data = {}

        def match_and_set(label, val):
            if not val or val.strip() in ["", "--", "N/A", "null", "None"]:
                return
            l = label.lower().strip()
            v = val.strip()
            if not v:
                return
            # Skip labels that are just numbers or irrelevant
            if l.isdigit() or l in ["s.no", "view", "status"]:
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

        # 1. Parse <dt>/<dd> pairs (General info, Admin info cards)
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                match_and_set(label, val)

        # 2. Parse <strong> + <p class="text-muted"> pairs (Contacts card)
        for strong in soup.find_all('strong'):
            label = strong.get_text(strip=True)
            # The value is in the next <p> sibling
            next_p = strong.find_next_sibling('p')
            if next_p:
                val = next_p.get_text(strip=True)
                match_and_set(label, val)

        # 3. Parse table rows & cells (certificates, etc - fallback)
        for row in soup.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                for i in range(0, len(cols) - 1, 2):
                    label = cols[i].text.strip()
                    val = cols[i+1].text.strip()
                    match_and_set(label, val)

        # 4. Inspect input & select fields (fallback)
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
    data = request.json
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
    data = request.json
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
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        att_url = "https://samvidha.iare.ac.in/home?action=stud_att_STD"
        resp = session.get(att_url, headers=HEADERS, timeout=15)
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

@app.route('/api/biometric', methods=['POST'])
def get_biometric():
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    session = do_fast_login(roll, password)
    
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
        
    try:
        bio_url = "https://samvidha.iare.ac.in/home?action=std_bio"
        resp = session.get(bio_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        target_table = None
        for t in soup.find_all('table'):
            if "In Time" in t.text and "Status" in t.text:
                target_table = t
                break
                
        if not target_table:
            return jsonify({"error": "Biometric table not found"}), 404
            
        rows = target_table.find_all('tr')
        biometric_data =[]
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 7:
                date_str = cols[3].text.strip()
                status = cols[9].text.strip()
                
                if date_str and "Date" not in date_str:
                    try:
                        # Convert 10-Apr-2026 -> 2026-04-10
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
    data = request.json
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

@app.route('/api/debug-profile', methods=['POST'])
def debug_profile():
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    if not roll or not password:
        return jsonify({"error": "Missing credentials"}), 400
    session = do_fast_login(roll, password)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        prof_url = "https://samvidha.iare.ac.in/home?action=profile"
        resp = session.get(prof_url, headers=HEADERS, timeout=15)
        scraped = scrape_profile_data(session)
        return jsonify({
            "success": True,
            "scraped_fields": scraped,
            "raw_html_length": len(resp.text),
            "raw_html_preview": resp.text[:5000]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "IARE Backend Service Running ULTRA FAST"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
