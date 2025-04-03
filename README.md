# VoxVision

VoxVision is an assistive AI-powered system designed to help visually impaired individuals interact with their surroundings through speech-based commands. The system processes voice inputs, classifies the request, and provides appropriate responses using a combination of NLP, object detection, and text-to-speech technologies.

## Features

- **Speech-to-Text Processing**: Converts user speech into text.
- **NLP-based Command Classification**: Distinguishes between object detection and general queries.
- **Object Detection**: Captures and processes images using ESP-32 Cam for object recognition.
- **Chatbot Functionality**: Answers general queries via the ChatGPT API.
- **Text-to-Speech Response**: Converts the processed response back into audio for the user.

## Workflow

The following workflow outlines the process VoxVision follows:

1. **Speech Input**: The system receives user input as a speech command.
2. **Audio Processing**: The input is saved as an `.mp4` file and converted to text using speech-to-text technology.
3. **NLP Classification**: The transcribed text is classified by an NLP model into one of the two categories:
   - **Object Detection**
   - **Chatting (General Queries)**
4. **Processing the Request**:
   - If the command is for **object detection**, an image is captured from the ESP-32 Cam, saved, and sent along with the prompt to the ChatGPT API for analysis.
   - If the command is a **general query**, the text is directly sent to the ChatGPT API for a response.
5. **Response Generation**:
   - The final answer is received and converted into speech using Whisper.
   - The audio response is saved as an `.mp3` file.
6. **Output Delivery**: The final audio is played through the front-end website for the user.

## Technologies Used

- **Hardware**:
  - ESP-32 Cam for image capture
- **Software & APIs**:
  - OpenAI Whisper (Speech-to-Text)
  - NLP model for classification
  - ChatGPT API for response generation
  - Text-to-Speech conversion

## Setup Instructions

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/VoxVision.git
   cd VoxVision
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Configure API keys for OpenAI services.
4. Setup your esp-32 camera and change the url in chatting.py
5. Run ngrok and change the ngrok link in index.html
6. Run the application:
   ```sh
   python main.py
   ```
7.  Run the application:
   ```sh
   python chatting.py
   ```
7. Open the ngrok url in your browser
