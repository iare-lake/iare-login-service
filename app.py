import os
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__)
CORS(app)

# --- CORE LOGIC ---

def get_attendance_fast(roll, password, just_verify=False):
    """
    If just_verify=True, returns Boolean (Login Success/Fail).
    If just_verify=False, returns Attendance Data (JSON).
    """
    with sync_playwright() as p:
        # Launch lightweight Chromium
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # Create context with realistic User Agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        # [SPEED HACK] BLOCK Images, CSS, Fonts
        # This reduces data usage by 90% and speeds up loading by 3x
        page.route("**/*", lambda route: route.abort() 
                   if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
                   else route.continue_())

        try:
            # 1. Login
            page.goto("https://samvidha.iare.ac.in/index.php", timeout=15000)
            
            # Fill form
            page.fill("input[name='txt_uname']", roll)
            page.fill("input[name='txt_pwd']", password)
            
            # Click submit and wait for URL change (max 10s)
            with page.expect_navigation(url="**/home**", timeout=10000):
                page.click("input[name='but_submit']")

            # If we are here, Login was successful (URL changed to home)
            if just_verify:
                browser.close()
                return True

            # 2. Go to Attendance Page
            page.goto("https://samvidha.iare.ac.in/home?action=stud_att_STD", timeout=10000)
            
            # Check if table exists
            if page.locator("table").filter(has_text="Course Name").count() == 0:
                browser.close()
                return {"error": "Attendance table not found"}

            # 3. Scrape Data
            # We use Playwright's locator API which is faster than BS4 here
            rows = page.locator("table").filter(has_text="Course Name").locator("tr").all()
            
            attendance_data = []
            # Skip header row (start from index 1)
            for row in rows[1:]:
                cols = row.locator("td").all()
                if len(cols) >= 8:
                    attendance_data.append({
                        "subject": cols[2].inner_text().strip(),
                        "total": cols[5].inner_text().strip(),
                        "present": cols[6].inner_text().strip(),
                        "percent": cols[7].inner_text().strip()
                    })

            browser.close()
            return {"success": True, "data": attendance_data}

        except Exception as e:
            browser.close()
            print(f"Error: {e}")
            if just_verify: return False
            return {"error": str(e)}

# --- ROUTES ---

@app.route('/api/verify', methods=['POST'])
def verify_user():
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    
    if not roll or not password:
        return jsonify({"valid": False, "error": "Missing credentials"}), 400

    is_valid = get_attendance_fast(roll, password, just_verify=True)
    return jsonify({"valid": is_valid})

@app.route('/api/attendance', methods=['POST'])
def get_attendance():
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    
    result = get_attendance_fast(roll, password, just_verify=False)
    
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/download', methods=['POST'])
def proxy_download():
    # Your existing download logic works fine, keeping it as is
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
            return jsonify({"error": "File not found on server"}), 404
            
        headers = { "Content-Disposition": f"attachment; filename={filename}", "Content-Type": content_type }
        return Response(remote.iter_content(chunk_size=1024), headers=headers, status=200)
    except:
        return jsonify({"error": "Server Error"}), 500

@app.route('/')
def home():
    return "IARE Backend Service Running"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
