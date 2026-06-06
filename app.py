import os
import sys
import subprocess
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. AUTO-INSTALL MISSING LIBRARIES
# ==========================================
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"Installing missing package: {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_and_import("flask")
install_and_import("requests")
install_and_import("urllib3")

import requests
import urllib3
from flask import Flask, render_template, request, jsonify

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ==========================================
# 2. CONFIG
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "PASTE_YOUR_API_KEY_HERE")

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")       # your Gmail
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") # Gmail App Password
AGENT_EMAIL = os.environ.get("AGENT_EMAIL")     # owner's email

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
11. Keep every response under 3 lines. Ask only one question at a time. Never ask multiple questions in one message. Short and conversational like texting.

Remember: You represent a professional real estate agency. Every lead matters."""

conversation_history = {}
emailed_sessions = set()

# ==========================================
# 3. LEAD EXTRACTION
# ==========================================
def extract_lead_info(history):
    full_text = " ".join([m["content"] for m in history])
    email = re.findall(r'[\w.-]+@[\w.-]+\.\w+', full_text)
    phone = re.findall(r'[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]', full_text)
    return {
        "email": email[-1] if email else None,
        "phone": phone[-1] if phone else None,
    }

# ==========================================
# 4. EMAIL SENDER
# ==========================================
def send_lead_email(session_id, history):
    if not SMTP_EMAIL or not AGENT_EMAIL or not SMTP_PASSWORD:
        print("Email config missing. Skipping email.")
        return

    lead = extract_lead_info(history)

    transcript = ""
    for msg in history[2:]:
        role = "Visitor" if msg["role"] == "user" else "Alex"
        transcript += f"{role}: {msg['content']}\n\n"

    body = f"""
NEW LEAD FROM ALEX CHATBOT
==========================
Email detected:  {lead['email'] or 'Not provided'}
Phone detected:  {lead['phone'] or 'Not provided'}
Session ID:      {session_id}

FULL CONVERSATION:
------------------
{transcript}
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = AGENT_EMAIL
    msg["Subject"] = "🏠 New Lead from Alex - Real Estate Chatbot"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, AGENT_EMAIL, msg.as_string())
            print(f"Lead email sent for session {session_id}")
    except Exception as e:
        print(f"Email failed: {e}")

# ==========================================
# 5. GEMINI API
# ==========================================
def ask_gemini(history):
    url = f"https://gemini-proxy.parjovanpreetkaur.workers.dev/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    contents = []
    for msg in history:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })

    payload = {"contents": contents}

    try:
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
# 6. FLASK ROUTES
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

    # Send email once when both email and phone are detected
    lead = extract_lead_info(conversation_history[session_id])
    if lead["email"] and lead["phone"] and session_id not in emailed_sessions:
        send_lead_email(session_id, conversation_history[session_id])
        emailed_sessions.add(session_id)

    return jsonify({"response": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
