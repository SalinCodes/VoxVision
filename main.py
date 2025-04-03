import sys
import uuid
import os
import base64
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pyttsx3
import openai
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
import re
import subprocess

# ---------------------------
# Auto-detect ngrok public URL
# ---------------------------
def get_ngrok_url():
    """
    Query ngrok's local API to retrieve the public URL.
    Returns the HTTPS public URL if available, or None otherwise.
    """
    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        tunnels = response.json().get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                return tunnel.get("public_url")
    except Exception as e:
        print("Could not retrieve ngrok URL:", e)
    return None

NGROK_URL = get_ngrok_url()
if NGROK_URL:
    print("Detected ngrok URL:", NGROK_URL)
else:
    print("ngrok URL not detected. Falling back to request.host_url.")

# ---------------------------
# Initialize Flask and SocketIO
# ---------------------------
app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------
# Initialize pyttsx3 for speech synthesis
# ---------------------------
engine = pyttsx3.init()
engine.setProperty("rate", 150)
engine.setProperty("volume", 1.0)

# Ensure required directories exist
os.makedirs("static/audio", exist_ok=True)

# ---------------------------
# Load the Intent Classifier Model
# ---------------------------
MODEL_PATH = r"codes\intent_classifier_model"
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()

# Load the OpenAI API key
import openai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=api_key)

# Function to predict the task
def predict_task(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_class = torch.argmax(logits, dim=1).item()

    # Map the predicted class to the correct label
    label_map = {0: "Object Detection", 1: "Chatting"}
    predicted_intent = label_map.get(predicted_class, "Unknown task")
    
    print(f"🧠 Predicted intent: {predicted_intent} for text: '{text}'")
    return predicted_intent


# ---------------------------
# OpenAI Communication
# ---------------------------

def get_openai_response(text, intent):
    print(f"🔄 Sending to OpenAI Flask app with intent: {intent}")
    openai_flask_url = "http://localhost:5001/send_to_openai"
    data = {"text": text, "intent": intent}  # Send intent along with text

    try:
        response = requests.post(openai_flask_url, json=data, timeout=30)  # Added timeout
        
        if response.status_code == 200:
            response_data = response.json()
            # Extract both the response text and image_processed flag
            response_text = response_data.get("response", "No response from OpenAI")
            image_processed = response_data.get("image_processed", False)
            return response_text, image_processed
        else:
            error_msg = f"Error from OpenAI Flask app: {response.status_code} - {response.text}"
            print(f"❌ {error_msg}")
            return error_msg, False
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error to OpenAI Flask app: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg, False


# ---------------------------
# Speech Synthesis
# ---------------------------
def generate_speech(text):
    """Generate speech using OpenAI's TTS and save as an MP3 file."""
    filename = f"speech_{uuid.uuid4()}.mp3"
    filepath = os.path.join("static/audio", filename)

    try:
        response = client.audio.speech.create(
            model="tts-1",  # Use "tts-1-hd" for higher quality
            voice="echo",  # Available voices: alloy, echo, fable, onyx, nova, shimmer
            input=text
        )

        with open(filepath, "wb") as f:
            f.write(response.content)

        if not os.path.exists(filepath):
            print(f"❌ Error: File {filepath} was not created!")
            return None

        print(f"✅ Speech file saved: {filepath}")
        return filename

    except Exception as e:
        print(f"❌ Error generating speech: {e}")
        return None


# ---------------------------
# WebSocket Event: Process Audio
# ---------------------------
@socketio.on("process_audio")
def handle_audio(data):
    try:
        print("🔹 Received process_audio WebSocket event")
        audio_data = data.get("audio_data")
        if not audio_data:
            print("❌ No audio data received")
            emit("error", {"error": "No audio data received"})
            return

        # Save and transcribe audio
        audio_filename = f"audio_{uuid.uuid4()}.wav"
        audio_path = os.path.join("static/audio", audio_filename)
        
        with open(audio_path, "wb") as audio_file:
            audio_file.write(base64.b64decode(audio_data))

        # Transcribe using OpenAI Whisper API
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
            )

        user_text = transcription.text
        processed_text = re.sub(r"(?i)stop recording", "", user_text).strip()
        print(f"🎤 Transcription: {processed_text}")

        # Determine intent
        intent = predict_task(processed_text)
        print(f"🧠 Intent detected: {intent}")

        # Get response and image processing status
        openai_response, image_processed = get_openai_response(processed_text, intent)
        print(f"🖼️ Image processed: {image_processed}")

        # Generate speech from response
        speech_filename = generate_speech(openai_response)

        if not speech_filename:
            emit("error", {"error": "Failed to generate speech file"})
            return

        host_url = NGROK_URL if NGROK_URL else "http://localhost:5000/"
        full_audio_url = f"{host_url.rstrip('/')}/static/audio/{speech_filename}"
        
        print(f"✅ Sending processed audio: {full_audio_url}")
        emit("audio_processed", {
            "text": openai_response, 
            "audio_url": full_audio_url, 
            "intent": intent,
            "image_processed": image_processed
        })
        print(f"✅ Audio processed and sent to client")

    except Exception as e:
        print(f"❌ Error in handle_audio: {str(e)}")
        emit("error", {"error": str(e)})


# ---------------------------
# HTTP Route to Serve Audio Files
# ---------------------------
@app.route("/static/audio/<filename>")
def serve_audio(filename):
    return send_from_directory("static/audio", filename)

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------
# Main Entry Point
# ---------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)