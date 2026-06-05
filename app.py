import os
import sys
import subprocess

# ==========================================
# 1. AUTO-INSTALL MISSING LIBRARIES
# ==========================================
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"Installing missing package: {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Check and install required packages automatically
install_and_import("flask")
install_and_import("requests")
install_and_import("urllib3")

# Import them safely after confirming installation
import requests
import urllib3
from flask import Flask, render_template, request, jsonify

# ==========================================
# 2. FLASK APP & API SETUP
# ==========================================

# Disable the red warning text for bypassing SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Replace this string with your actual Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "PASTE_YOUR_API_KEY_HERE")

SYSTEM_PROMPT = """You are Alex, a professional AI real estate assistant powered by Atlas AI. You help website visitors 24/7 with all real estate needs.

You handle:
- Buying a home
- Selling a home
- Renting a property
- Relocating to a new city
- Investment properties
- Luxury homes
- First time buyers
- New construction

Your job:
1. Greet warmly and ask if they are buying, selling, renting, relocating or investing
2. Ask smart qualifying questions — budget, timeline, location, property type, bedrooms
3. Score every lead as Hot, Warm or Cold based on urgency
4. Collect name, email and phone naturally in conversation
5. Book appointments by asking preferred date and time
6. Respond in whatever language the visitor writes in automatically
7. Never say you don't know — always give a helpful answer
8. Handle objections naturally — if they say just browsing, keep them engaged
9. Be warm, human and professional — never robotic or pushy
10. End every conversation with contact info collected and a lead summary

Remember: You represent a professional real estate agency. Every lead matters."""

conversation_history = {}

def ask_gemini(history):
    # Using your Cloudflare Worker to bypass the ISP block completely
    url = f"https://gemini-proxy.parjovanpreetkaur.workers.dev/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    # Format the history for the API
    contents = []
    for msg in history:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })

    payload = {"contents": contents}

    try:
        # verify=False prevents local certificate errors
        # timeout=60 handles slower network connections
        response = requests.post(
            url, 
            json=payload, 
            headers={"Content-Type": "application/json"},
            timeout=60,
            verify=False 
        )
        
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
        
    except requests.exceptions.HTTPError as errh:
        return f"HTTP Error: {errh} - Check if your API key is correct."
    except requests.exceptions.ConnectionError:
        return "Error Connecting: Please check your internet connection."
    except requests.exceptions.Timeout:
        return "Timeout Error: The request took too long. Try again."
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# 3. FLASK ROUTES
# ==========================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    session_id = data.get("session_id", "default")

    if session_id not in conversation_history:
        conversation_history[session_id] = [
            {"role": "user", "content": SYSTEM_PROMPT},
            {"role": "model", "content": "Understood. I am Alex, a professional real estate AI assistant. Ready to help visitors 24/7."}
        ]

    conversation_history[session_id].append({
        "role": "user",
        "content": user_message
    })

    reply = ask_gemini(conversation_history[session_id])

    conversation_history[session_id].append({
        "role": "model",
        "content": reply
    })

    return jsonify({"response": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
