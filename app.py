import os
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from playwright.sync_api import sync_playwright

app = Flask(__name__)
CORS(app)

# --- THE SPEED HACK ---
# Keep the browser open in memory globally so we don't 
# waste 10 seconds booting Chromium for every single request.
playwright_instance = None
browser = None

def get_browser():
    global playwright_instance, browser
    if browser is None:
        print("[-] Booting Global Browser Instance...")
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    return browser

# --- CORE LOGIC ---

def get_attendance_fast(roll, password, just_verify=False):
    b = get_browser()
    # Create a fresh, lightweight tab/context for this specific user
    context = b.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    # SUPER SPEED: Block heavy resources
    page.route("**/*", lambda route: route.abort() 
               if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
               else route.continue_())

    try:
        page.goto("https://samvidha.iare.ac.in/index.php", timeout=30000)
        
        page.fill("[name='txt_uname']", roll)
        page.fill("[name='txt_pwd']", password)
        
        # THE FIX: Removed 'input' from the locator so it clicks the <button> tag properly.
        with page.expect_navigation(url="**/home**", timeout=20000):
            page.locator("[name='but_submit']").click()

        if just_verify:
            context.close()
            return True

        page.goto("https://samvidha.iare.ac.in/home?action=stud_att_STD", timeout=20000)
        
        if page.locator("table").filter(has_text="Course Name").count() == 0:
            context.close()
            return {"error": "Attendance table not found"}

        rows = page.locator("table").filter(has_text="Course Name").locator("tr").all()
        
        attendance_data = []
        for row in rows[1:]:
            cols = row.locator("td").all()
            if len(cols) >= 8:
                attendance_data.append({
                    "subject": cols[2].inner_text().strip(),
                    "total": cols[5].inner_text().strip(),
                    "present": cols[6].inner_text().strip(),
                    "percent": cols[7].inner_text().strip()
                })

        context.close()
        return {"success": True, "data": attendance_data}

    except Exception as e:
        context.close()
        return {"error": str(e)}

# --- ROUTES ---

@app.route('/api/verify', methods=['POST'])
def verify_user():
    data = request.json
    roll = data.get('roll')
    password = data.get('password')
    
    if not roll or not password:
        return jsonify({"valid": False, "error": "Missing credentials"}), 400

    result = get_attendance_fast(roll, password, just_verify=True)
    
    if isinstance(result, dict) and "error" in result:
        return jsonify({"valid": False, "error": result["error"]})
        
    return jsonify({"valid": True})

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
