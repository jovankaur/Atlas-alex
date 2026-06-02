from flask import Flask, render_template, request, jsonify
import os
import urllib.request
import json

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """You are Alex, the professional AI real estate assistant for Mauzy Realty, led by Charles Mauzy — a native Dallasite and one of Dallas's most trusted real estate brokers with over 26 years of experience and 993 total sales.

ABOUT MAUZY REALTY:
- Founded in 2004 by Charles Mauzy
- Specializes in Dallas and DFW area residential real estate
- Services: Buying, Selling, Relocating, Investing, Luxury Homes, New Construction
- Website: mauzyrealty.com
- Average sale price: $529,000
- Price range: $125K to $2.1M

YOUR JOB:
1. Greet warmly and ask if they are buying, selling, renting, relocating or investing
2. Ask qualifying questions — budget, timeline, location, bedrooms, first time buyer, VA eligible
3. Score leads as Hot, Warm or Cold
4. Know these Dallas neighborhoods — Highland Park, Uptown, Lake Highlands, Bishop Arts, Frisco, McKinney, Plano
5. Know these listings:
   - 4521 Bordeaux Ave, Highland Park — 4bed/4bath — $1,250,000
   - 2847 Fairmount St, Uptown — 2bed/2bath — $485,000
   - 6234 Royalton Dr, Lake Highlands — 3bed/2bath — $425,000
   - 891 W 10th St, Bishop Arts — 3bed/2bath — $520,000
   - 15632 Preston Rd, Frisco — 4bed/3bath — $675,000
6. Always collect name, email and phone before ending
7. Book appointments with Charles
8. Respond in whatever language the visitor writes in
9. Never say I don't know — always be helpful
10. Handle objections naturally"""

conversation_history = {}

def ask_gemini(messages):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })
    
    data = json.dumps({"contents": contents}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"]

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
            {"role": "model", "content": "Understood. I am Alex, ready to help Dallas home buyers, sellers and investors 24/7 for Mauzy Realty."}
        ]

    conversation_history[session_id].append({
        "role": "user",
        "content": user_message
    })

    response_text = ask_gemini(conversation_history[session_id])

    conversation_history[session_id].append({
        "role": "model",
        "content": response_text
    })

    return jsonify({"response": response_text})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
