# This project is a Flask-based web application that allows users to:
1. Upload a video in any language.
2. Transcribe the audio using Faster-Whisper.
3. Translate the transcription into multiple languages (Hindi, Kannada, Telugu, Tamil, Malayalam, Marathi, Spanish, French, Korean, etc.) using Google Translate.
4. Generate translated audio using gTTS.
5. Merge the translated audio back into the original video, keeping it in sync.
6. Watch the video with translated audio.

# Features
1. Upload a video with original audio.
2. Auto-detect and transcribe speech.
3. Translate into multiple languages.
4. Generate new audio tracks with proper syncing.
5. Replace original audio in the video with selected translation.
6. Watch output directly in browser.

# Usage
1. pip install -r requirement.txt
2. Run the Flask app:
   python app.py
3. Open the browser at:
    http://127.0.0.1:5000
4. Upload a video.
5. Choose a target language (Hindi, Kannada, Tamil, Spanish, etc.).
6. Wait for processing.
7. Watch the video with translated audio.

# Supported Languages
1. Hindi 🇮🇳
2. Kannada 🇮🇳
3. Telugu 🇮🇳
4. Tamil 🇮🇳
5. Malayalam 🇮🇳
6. Marathi 🇮🇳
7.Spanish 🇪🇸
8. French 🇫🇷
9. Korean 🇰🇷
10. English 🇬🇧
