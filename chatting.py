import os
import openai
import requests
import base64
import time  # Add time module import
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import cv2
from PIL import Image, ImageDraw  # Add PIL imports

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ API key is missing. Set it as an environment variable: OPENAI_API_KEY")

client = openai.OpenAI(api_key=api_key)

# Function to retrieve ngrok URL
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
        print("❌ Could not retrieve ngrok URL:", e)
    return None

# Get the ngrok URL (if available)
NGROK_URL = get_ngrok_url()
if NGROK_URL:
    print(f"✅ Detected ngrok URL: {NGROK_URL}")
else:
    print("❌ ngrok URL not detected. Falling back to request.host_url.")

# Function to convert an image file to base64
def encode_image_to_base64(image_path):
    try:
        if not os.path.exists(image_path):
            print(f"❌ Image file not found: {image_path}")
            return None
        
        # Check file size
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            print(f"❌ Image file is empty: {image_path}")
            return None
            
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            
        if not encoded_string:
            print("❌ Encoded string is empty")
            return None
            
        print(f"✅ Successfully encoded image ({len(encoded_string)} characters)")
        
        # Verify the encoded string is valid base64
        try:
            # Try to decode a small part to verify it's valid base64
            base64.b64decode(encoded_string[:100])
            return encoded_string
        except Exception as e:
            print(f"❌ Invalid base64 encoding: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Update the ESP32_CAM_URL to be configurable or have a fallback
ESP32_CAM_URL = os.getenv("ESP32_CAM_URL", "http://172.20.10.2/capture")

# Update the base directory path to match the working test script
base_dir = os.path.join(os.getcwd(), "static", "images")
os.makedirs(base_dir, exist_ok=True)

# Add this line to print the actual directory path for debugging
print(f"📁 Image directory path: {os.path.abspath(base_dir)}")


def capture_image():
    try:
        # Ensure the directory exists
        os.makedirs(base_dir, exist_ok=True)
        
        # Use absolute path for the image file
        image_filename = os.path.abspath(os.path.join(base_dir, f"esp32_capture_{int(time.time())}.jpg"))
        
        print(f"📸 Will save image to: {image_filename}")
        
        # Try main URL first
        print(f"📸 Attempting to capture image from ESP32-CAM at {ESP32_CAM_URL}...")
        
        try:
            response = requests.get(ESP32_CAM_URL, stream=True, timeout=5)
            if response.status_code == 200:
                with open(image_filename, "wb") as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                
                # Verify the image was saved correctly
                if os.path.exists(image_filename) and os.path.getsize(image_filename) > 0:
                    print(f"✅ Image saved as: {image_filename} ({os.path.getsize(image_filename)} bytes)")
                    
                    # Try to open the image with PIL to verify it's valid
                    try:
                        from PIL import Image
                        img = Image.open(image_filename)
                        img.verify()  # Verify it's a valid image
                        print(f"✅ Image verified: {img.format} {img.size}x{img.mode}")
                        return image_filename
                    except Exception as e:
                        print(f"❌ Invalid image file: {e}")
                        # Continue to fallback
                else:
                    print(f"❌ Image file is empty or not saved")
            else:
                print(f"❌ Failed to capture image. Status code: {response.status_code}")
        except Exception as e:
            print(f"❌ Error capturing image: {e}")
        
        # If we reach here, try to use the existing esp_32.jpg
        existing_image = os.path.abspath(os.path.join(base_dir, "esp_32.jpg"))
        if os.path.exists(existing_image) and os.path.getsize(existing_image) > 0:
            print(f"✅ Using existing image: {existing_image}")
            return existing_image
        
        # If both options fail, return None
        print("❌ No valid image available")
        return None

    except Exception as e:
        print(f"❌ Unexpected error in capture_image: {e}")
        return None

# Add this route to check server status
@app.route("/status")
def status():
    try:
        # Return a simple JSON response
        return jsonify({
            "status": "running",
            "timestamp": time.time()
        })
    except Exception as e:
        print(f"❌ Error in status endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Update the send_to_openai function
@app.route("/send_to_openai", methods=["POST"])
def send_to_openai():
    data = request.get_json()
    text = data.get("text")
    intent = data.get("intent") 
    
    if not text:
        return jsonify({"error": "Missing text"}), 400
    
    if not intent:
        print("⚠️ No intent provided, defaulting to 'Chatting'")
        intent = "Chatting"

    image_path = None
    image_processed = False
    print(f"🔍 Processing intent: {intent}")

    # Only attempt to capture image for Object Detection intent
    if intent == "Object Detection":
        print("📸 Attempting to capture image for object detection...")
        try:
            image_path = capture_image()
            
            if image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                print(f"✅ Image captured successfully: {image_path}")
                image_processed = True
            else:
                print(f"❌ Image capture failed or file is empty")
                return jsonify({
                    "response": "I tried to look at what you're asking about, but I'm having trouble with the camera. Could you please try again or ask me something else?",
                    "image_processed": False
                })
        except Exception as e:
            print(f"❌ Error during image capture: {e}")
            return jsonify({
                "response": "I encountered an error while trying to capture an image. Could you please try again?",
                "image_processed": False
            })

    try:
        # For object detection, use a more specific prompt
        if intent == "Object Detection":
            prompt_text = f"""The user asked: '{text}'. 
            Analyze the image I'm sending and describe what you see in detail. 
            Focus on identifying objects, people, text, or anything else visible in the image.
            Respond directly to the user's question about what they're looking at."""
        else:
            prompt_text = f"""{text}, answer in detail. Don't give any direct signs that you are an AI model, 
                            and don't mention OpenAI. Just act like a human and answer the question. If the question is about currency,
                            only answer the question about nepali currency. If the question is about other currency, you can say "I'm sorry, I can only help with nepali currency." """
        
        message_content = [{"type": "text", "text": prompt_text}]
        
        # Only add image if we have a valid image path and intent is Object Detection
        if image_path and os.path.exists(image_path) and intent == "Object Detection":
            print(f"📸 Processing image for analysis: {image_path}")
            try:
                # Get file size for debugging
                file_size = os.path.getsize(image_path)
                print(f"📊 Image file size: {file_size} bytes")
                
                if file_size > 0:
                    base64_image = encode_image_to_base64(image_path)
                    if base64_image:
                        image_content = {"url": f"data:image/jpeg;base64,{base64_image}"}
                        message_content.append({"type": "image_url", "image_url": image_content})
                        print(f"✅ Successfully added image to message content")
                        image_processed = True
                    else:
                        print("⚠️ Failed to encode image to base64")
                        return jsonify({
                            "response": "I tried to analyze what's in front of you, but I'm having trouble processing the image. Could you please try again?",
                            "image_processed": False
                        })
                else:
                    print("⚠️ Image file is empty")
                    return jsonify({
                        "response": "I tried to see what's in front of you, but the camera didn't capture anything. Could you please try again?",
                        "image_processed": False
                    })
            except Exception as e:
                print(f"❌ Error processing image: {e}")
                return jsonify({
                    "response": f"I encountered an error while trying to see what's in front of you. Could you please try again?",
                    "image_processed": False
                })

        print(f"🔄 Sending message to OpenAI with {len(message_content)} content items")
        
        openai_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message_content}],
        )
        
        response_text = openai_response.choices[0].message.content
        print(f"✅ Received response from OpenAI about the image/query")
        
        return jsonify({
            "response": response_text, 
            "image_processed": image_processed
        })

    except Exception as e:
        error_message = f"Error in send_to_openai: {str(e)}"
        print(f"❌ {error_message}")
        return jsonify({"error": error_message, "image_processed": False}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)