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
        return jsonify({"valid": True})
    return jsonify({"valid": False, "error": "Invalid credentials"})

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
                status = cols[6].text.strip()
                
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

@app.route('/')
def home():
    return "IARE Backend Service Running ULTRA FAST"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
