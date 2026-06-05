import os
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# Initialize the Gemini Client
# The SDK automatically looks for GEMINI_API_KEY in your environment variables
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_PROMPT = """You are Alex, a professional AI real estate assistant. 
Follow these rules:
1. Greet warmly and ask if they are buying, selling, renting, relocating or investing.
2. Ask qualifying questions (budget, timeline, location).
3. Score leads as Hot, Warm, or Cold.
4. Collect contact info naturally.
5. Be human, warm, and professional."""

# Using a dictionary to store chat sessions
conversation_history = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    session_id = data.get("session_id", "default")

    # Initialize chat session if it doesn't exist
    if session_id not in conversation_history:
        conversation_history[session_id] = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            )
        )

    try:
        # Use the SDK's built-in chat management
        response = conversation_history[session_id].send_message(user_message)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"response": f"Connection error: {str(e)} Please check your network."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
