import os
import sys
import subprocess
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

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

GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
AGENT_EMAIL = os.environ.get("AGENT_EMAIL")

SYSTEM_PROMPT = """You are Alex, a professional real estate AI assistant. You are direct, warm and efficient. Like a smart receptionist, not a salesperson.

Your job:
1. Ask what they need — buying, selling, renting, investing
2. Ask location
3. Ask property type
4. Ask budget
5. Ask timeline
6. Ask for name, email and phone number together in one message
7. End with: "Perfect. Our agent will be in touch with you shortly!"

Rules:
- Maximum 2 sentences per response
- One question at a time
- Never say fantastic, great, wonderful, excellent or any fake praise
- Never repeat back everything they said
- Respond in whatever language the visitor uses
- Be warm but brief — like texting a helpful friend
- Never show lead score in chat
- Once you have name, email and phone — say: "Perfect. Our agent will be in touch with you shortly!"
- If the visitor asks a real estate question, answer briefly then continue qualification
- If unrelated to real estate, politely redirect back to property needs

Remember: Every second counts. Keep it short."""

conversation_history = {}
emailed_sessions = set()

def extract_lead_info(history):
    full_text = " ".join([m["content"] for m in history])
    email = re.findall(r'[\w.-]+@[\w.-]+\.\w+', full_text)
    phone = re.findall(r'[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]', full_text)
    name = None
    for msg in history:
        if msg["role"] == "user":
            text = msg["content"].strip()
            if (
                len(text.split()) <= 3
                and "@" not in text
                and not any(char.isdigit() for char in text)
            ):
                name = text
    return {
        "name": name,
        "email": email[-1] if email else None,
        "phone": format_phone(phone[-1]) if phone else None,
    }

def format_phone(phone):
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) > 10:
        country = digits[:-10]
        local = digits[-10:]
        return f"+{country} ({local[:3]}) {local[3:6]}-{local[6:]}"
    return phone

def is_valid_phone(phone):
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10

def send_lead_email(session_id, history):
    if not SMTP_EMAIL or not AGENT_EMAIL or not SMTP_PASSWORD:
        print("Email config missing. Skipping email.")
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lead = extract_lead_info(history)

    transcript = ""
    for msg in history[2:]:
        role = "Visitor" if msg["role"] == "user" else "Alex"
        transcript += f"{role}: {msg['content']}\n\n"

    body = f"""
NEW LEAD FROM ALEX CHATBOT
==========================
Name detected:   {lead['name'] or 'Not provided'}
Email detected:  {lead['email'] or 'Not provided'}
Phone detected:  {lead['phone'] or 'Not provided'}
Time detected:   {timestamp}
Session ID:      {session_id}

FULL CONVERSATION:
------------------
{transcript}
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = AGENT_EMAIL
    msg["Subject"] = "New Lead from Alex - Real Estate Chatbot"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, AGENT_EMAIL, msg.as_string())
            print(f"Lead email sent for session {session_id}")
    except Exception as e:
        print(f"Email failed: {e}")

def call_gemini(api_key, contents):
    url = f"https://gemini-proxy.parjovanpreetkaur.workers.dev/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {"contents": contents}
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

def ask_gemini(history):
    contents = []
    for msg in history:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })

    # Try first key
    try:
        return call_gemini(GEMINI_API_KEY_1, contents)
    except Exception as e1:
        print(f"Key 1 failed: {e1}. Trying key 2...")

    # Try second key
    try:
        return call_gemini(GEMINI_API_KEY_2, contents)
    except Exception as e2:
        print(f"Key 2 failed: {e2}.")
        return "Sorry, I'm assisting another client right now. Give me just a moment and try again! 🏠"

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

    lead = extract_lead_info(conversation_history[session_id])
    if (
        lead["email"]
        and lead["phone"]
        and is_valid_phone(lead["phone"])
        and session_id not in emailed_sessions
    ):
        send_lead_email(session_id, conversation_history[session_id])
        emailed_sessions.add(session_id)

    return jsonify({"response": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
