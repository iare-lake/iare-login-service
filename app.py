import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

app = Flask(__name__)
CORS(app)

def verify_credentials(roll: str, password: str) -> bool:
    screenshot_path = f"debug_error_{roll}.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-infobars",
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            bypass_csp=True,
            ignore_https_errors=True,
            java_script_enabled=True,
        )
        
        context.route("**/*.{png,jpg,jpeg,gif,svg,css}", lambda route: route.abort())
        
        page = context.new_page()
        
        try:
            print(f"[START] Verifying roll: {roll}")
            
            page.goto("https://samvidha.iare.ac.in/index.php", 
                      wait_until="domcontentloaded", 
                      timeout=30000)
            
            print("→ Waiting for username field...")
            page.wait_for_selector("input[name='txt_uname']", timeout=20000)
            page.fill("input[name='txt_uname']", roll.strip())
            
            print("→ Filling password...")
            page.fill("input[name='txt_pwd']", password.strip())
            
            print("→ Attempting to submit...")
            try:
                page.click("input[name='but_submit']", timeout=12000)
            except PlaywrightTimeoutError:
                print("→ Name locator failed → trying text 'Sign In'...")
                page.click("text=Sign In", timeout=15000)
            
            print("→ Waiting for post-login state (redirect or content)...")
            try:
                page.wait_for_url("**/home**", timeout=30000)
                print("→ Redirect to /home detected → SUCCESS")
                return True
            except PlaywrightTimeoutError:
                print("→ No exact /home redirect → checking content keywords...")
                content = page.content().lower()
                success_keywords = ["logout", "sign out", "dashboard", "welcome", "attendance", "student portal", "profile"]
                if any(keyword in content for keyword in success_keywords):
                    print("→ Success keyword found → SUCCESS")
                    return True
                else:
                    print("→ No success keyword found → FAILED")
                    return False
        
        except Exception as e:
            print(f"[ERROR] Verification failed for {roll}: {str(e)}")
            try:
                page.screenshot(path=screenshot_path)
                print(f"→ Screenshot saved: {screenshot_path}")
            except:
                pass
            return False
        
        finally:
            # Silent suppression of Windows cleanup crash (harmless)
            try:
                context.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass

@app.route('/api/verify', methods=['POST'])
def verify_user():
    data = request.get_json(silent=True) or {}
    roll = data.get('roll')
    password = data.get('password')

    if not roll or not password:
        return jsonify({"error": "Missing roll or password"}), 400

    is_valid = verify_credentials(roll, password)
    return jsonify({"valid": is_valid})

@app.route('/ping', methods=['GET'])
def ping():
    return "Awake!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True, threaded=False, use_reloader=False)