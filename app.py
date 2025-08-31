# import os
# import subprocess
# import json
# from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
# import whisper
# from deep_translator import GoogleTranslator
# from gtts import gTTS
# import uuid
# from werkzeug.utils import secure_filename
# from pydub import AudioSegment


# # -----------------------
# # Configuration
# # -----------------------
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # Whisper model selection: "base", "small", "medium", "large"
# WHISPER_MODEL_NAME = "small"

# # Supported languages mapping for UI -> translation/TTS codes
# SUPPORTED_LANGS = {
#     "en": {"name": "English", "ttscode": "en"},
#     "hi": {"name": "Hindi", "ttscode": "hi"},
#     "kn": {"name": "Kannada", "ttscode": "kn"},
#     "te": {"name": "Telugu", "ttscode": "te"},
#     "ta": {"name": "Tamil", "ttscode": "ta"},
#     "mr": {"name": "Marathi", "ttscode": "mr"},
#     "ml": {"name": "Malayalam", "ttscode": "ml"},
#     "es": {"name": "Spanish", "ttscode": "es"},
#     "fr": {"name": "French", "ttscode": "fr"},
#     "ko": {"name": "Korean", "ttscode": "ko"}
# }

# app = Flask(__name__)
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# # Load Whisper model (may take a while on first run)
# print("Loading Whisper model:", WHISPER_MODEL_NAME)
# whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
# print("Whisper loaded")

# # -----------------------
# # Utility helpers
# # -----------------------
# def extract_audio(video_path, out_wav_path):
#     """Extract audio from video using ffmpeg to WAV (16k/mono is fine for whisper)."""
#     # Convert to WAV PCM 16-bit 16k for whisper/stability
#     cmd = [
#         "ffmpeg", "-y",
#         "-i", video_path,
#         "-ar", "16000",
#         "-ac", "1",
#         "-vn",
#         out_wav_path
#     ]
#     subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     return out_wav_path

# def transcribe_with_whisper(wav_path):
#     """Transcribe and return whisper result dict (with segments)."""
#     result = whisper_model.transcribe(wav_path, language=None)  # let it detect
#     return result  # contains 'text', 'segments', 'language' (detected)

# def segments_to_vtt(segments, out_vtt_path):
#     """Write segments (start,end,text) to WebVTT file."""
#     def fmt_ts(s):
#         h = int(s // 3600)
#         m = int((s % 3600) // 60)
#         sec = s % 60
#         return f"{h:02d}:{m:02d}:{sec:06.3f}".replace('.',',').replace(',', '.')  # ensure dot
#     with open(out_vtt_path, "w", encoding="utf-8") as f:
#         f.write("WEBVTT\n\n")
#         for i, seg in enumerate(segments):
#             start = seg["start"]
#             end = seg["end"]
#             text = seg["text"].strip()
#             # WebVTT expects dot decimal seconds
#             f.write(f"{fmt_ts(start)} --> {fmt_ts(end)}\n")
#             f.write(text + "\n\n")
#     return out_vtt_path

# def translate_segment_texts(segments, target_lang_code):
#     """Translate each segment text and return new list of segments with translated text."""
#     translated = []
#     for seg in segments:
#         txt = seg["text"].strip()
#         try:
#             trans = GoogleTranslator(source='auto', target=target_lang_code).translate(txt)
#         except Exception as e:
#             print("Translation error:", e)
#             trans = txt
#         translated.append({"start": seg["start"], "end": seg["end"], "text": trans})
#     return translated

# def generate_aligned_tts_audio(segments, tts_lang_code, out_audio_path):
#     """
#     Generate aligned audio using gTTS per segment.
#     Each segment is time-stretched so that its duration matches the original.
#     """
#     full_audio = AudioSegment.silent(duration=0)

#     for seg in segments:
#         text = seg["text"].strip()
#         start_ms = int(seg["start"] * 1000)
#         end_ms = int(seg["end"] * 1000)
#         duration_ms = end_ms - start_ms

#         if not text:
#             full_audio += AudioSegment.silent(duration=duration_ms)
#             continue

#         try:
#             # Generate TTS for this segment
#             tmp_file = f"tmp_{uuid.uuid4().hex}.mp3"
#             gTTS(text=text, lang=tts_lang_code).save(tmp_file)

#             # Load TTS audio
#             tts_audio = AudioSegment.from_file(tmp_file, format="mp3")
#             os.remove(tmp_file)

#             # Export temporary wav
#             seg_wav = f"seg_{uuid.uuid4().hex}.wav"
#             tts_audio.export(seg_wav, format="wav")

#             # Stretch/compress with ffmpeg atempo filter
#             stretched_wav = f"stretched_{uuid.uuid4().hex}.wav"
#             actual_dur = len(tts_audio)
#             if actual_dur > 0:
#                 speed = actual_dur / duration_ms
#             else:
#                 speed = 1.0

#             # atempo only supports 0.5–2.0, so we chain if outside range
#             if speed < 0.5:
#                 speed = 0.5
#             elif speed > 2.0:
#                 speed = 2.0

#             cmd = [
#                 "ffmpeg", "-y",
#                 "-i", seg_wav,
#                 "-filter:a", f"atempo={speed}",
#                 stretched_wav
#             ]
#             subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

#             # Load back stretched audio
#             stretched_audio = AudioSegment.from_file(stretched_wav, format="wav")
#             os.remove(seg_wav)
#             os.remove(stretched_wav)

#             # Adjust final length (pad/trim tiny mismatch)
#             if len(stretched_audio) > duration_ms:
#                 stretched_audio = stretched_audio[:duration_ms]
#             else:
#                 stretched_audio += AudioSegment.silent(duration=(duration_ms - len(stretched_audio)))

#             full_audio += stretched_audio

#         except Exception as e:
#             print("TTS error:", e)
#             full_audio += AudioSegment.silent(duration=duration_ms)

#     full_audio.export(out_audio_path, format="mp3")
#     return out_audio_path


# # -----------------------
# # Routes
# # -----------------------
# @app.route("/", methods=["GET", "POST"])
# def index():
#     if request.method == "POST":
#         if "video" not in request.files:
#             return "No file part", 400
#         f = request.files["video"]
#         if f.filename == "":
#             return "No selected file", 400
#         # save uploaded file
#         safe_name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
#         video_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
#         f.save(video_path)
#         return redirect(url_for("player", filename=safe_name))
#     return render_template("index.html", supported_langs=SUPPORTED_LANGS)

# @app.route("/player/<path:filename>")
# def player(filename):
#     # Check that file exists
#     video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#     if not os.path.exists(video_path):
#         return "Video not found", 404
#     # Pass supported languages to template
#     return render_template("player.html", filename=filename, supported_langs=SUPPORTED_LANGS)

# @app.route("/uploads/<path:filename>")
# def uploaded_file(filename):
#     return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

# @app.route("/translate", methods=["POST"])
# def translate():
#     """
#     POST JSON expected:
#     {
#       "filename": "<uploaded file name>",
#       "to": "hi"   # target language code from SUPPORTED_LANGS
#     }
#     Returns JSON with paths to generated .vtt and .mp3 (if created) and detected source language.
#     """
#     data = request.get_json()
#     if not data or "filename" not in data or "to" not in data:
#         return jsonify({"error": "filename and to required"}), 400

#     filename = data["filename"]
#     to_lang = data["to"]
#     if to_lang not in SUPPORTED_LANGS:
#         return jsonify({"error": "unsupported target language"}), 400

#     video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#     if not os.path.exists(video_path):
#         return jsonify({"error": "video not found"}), 404

#     # Prepare working files
#     wav_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.wav")
#     extract_audio(video_path, wav_path)

#     # Transcribe (Whisper)
#     whisper_result = transcribe_with_whisper(wav_path)
#     detected_lang = whisper_result.get("language", "unknown")
#     segments = whisper_result.get("segments", [])
#     # Normalize segments to expected dict items: start,end,text
#     normalized = [{"start": s["start"], "end": s["end"], "text": s.get("text", "")} for s in segments]

#     # Translate segments
#     translated_segments = translate_segment_texts(normalized, to_lang)

#     # Save VTT for the target language
#     vtt_name = f"{filename}.{to_lang}.vtt"
#     vtt_path = os.path.join(app.config["UPLOAD_FOLDER"], vtt_name)
#     segments_to_vtt(translated_segments, vtt_path)

#     # Optionally produce a single TTS mp3 for the full translated text
#     tts_code = SUPPORTED_LANGS[to_lang]["ttscode"]
#     mp3_name = f"{filename}.{to_lang}.mp3"
#     mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_name)
#     tts_out = generate_aligned_tts_audio(translated_segments, tts_code, mp3_path)

#     # Return relative URLs so frontend can load them
#     vtt_url = url_for("uploaded_file", filename=vtt_name)
#     mp3_url = url_for("uploaded_file", filename=mp3_name) if tts_out else None

#     return jsonify({
#         "ok": True,
#         "detected_source_language": detected_lang,
#         "vtt": vtt_url,
#         "mp3": mp3_url
#     })

# if __name__ == "__main__":
#     app.run(debug=True)


import os
import subprocess
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
from werkzeug.utils import secure_filename
from pydub import AudioSegment


# -----------------------
# Configuration
# -----------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Whisper model selection: "base", "small", "medium", "large"
WHISPER_MODEL_NAME = "small"

# Supported languages mapping for UI -> translation/TTS codes
SUPPORTED_LANGS = {
    "en": {"name": "English", "ttscode": "en"},
    "hi": {"name": "Hindi", "ttscode": "hi"},
    "kn": {"name": "Kannada", "ttscode": "kn"},
    "te": {"name": "Telugu", "ttscode": "te"},
    "ta": {"name": "Tamil", "ttscode": "ta"},
    "mr": {"name": "Marathi", "ttscode": "mr"},
    "ml": {"name": "Malayalam", "ttscode": "ml"},
    "es": {"name": "Spanish", "ttscode": "es"},
    "fr": {"name": "French", "ttscode": "fr"},
    "ko": {"name": "Korean", "ttscode": "ko"}
}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Load Whisper model (may take a while on first run)
print("Loading Whisper model:", WHISPER_MODEL_NAME)
whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
print("Whisper loaded")


# -----------------------
# Utility helpers
# -----------------------
def extract_audio(video_path, out_wav_path):
    """Extract audio from video using ffmpeg to WAV (16k/mono is fine for whisper)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        "-vn",
        out_wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out_wav_path

def transcribe_with_whisper(wav_path):
    """Transcribe and return whisper result dict (with segments)."""
    result = whisper_model.transcribe(wav_path, language=None)  # let it detect
    return result  # contains 'text', 'segments', 'language' (detected)

def segments_to_vtt(segments, out_vtt_path):
    """Write segments (start,end,text) to WebVTT file."""
    def fmt_ts(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:06.3f}".replace('.',',').replace(',', '.')
    with open(out_vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            start = seg["start"]
            end = seg["end"]
            text = seg["text"].strip()
            f.write(f"{fmt_ts(start)} --> {fmt_ts(end)}\n")
            f.write(text + "\n\n")
    return out_vtt_path

def translate_segment_texts(segments, target_lang_code):
    """Translate each segment text and return new list of segments with translated text."""
    translated = []
    for seg in segments:
        txt = seg["text"].strip()
        try:
            trans = GoogleTranslator(source='auto', target=target_lang_code).translate(txt)
        except Exception as e:
            print("Translation error:", e)
            trans = txt
        translated.append({"start": seg["start"], "end": seg["end"], "text": trans})
    return translated

def _build_atempo_chain(ratio):
    """
    ffmpeg atempo supports 0.5..2.0. For ratios outside, chain multiple.
    We want new_duration ≈ target_duration.
    atempo=tempo => new_duration = old_duration / tempo.
    To reach target T from original D we set tempo = D/T.
    Here 'ratio' is D/T.
    """
    factors = []
    if ratio <= 0:
        return "atempo=1.0"
    # Bring ratio into (0.5..2.0) by chaining 0.5 or 2.0 as needed
    while ratio > 2.0:
        factors.append(2.0)
        ratio /= 2.0
    while ratio < 0.5:
        factors.append(0.5)
        ratio /= 0.5
    factors.append(ratio)
    # Merge to ffmpeg filter string
    return ",".join([f"atempo={f:.6f}" for f in factors])

def generate_aligned_tts_audio_timeline(segments, tts_lang_code, out_audio_path, original_total_ms):
    """
    Build a *timeline-accurate* dub track:
    - Insert silence up to each segment start.
    - TTS each segment.
    - Precisely time-stretch each segment to (end-start) with ffmpeg atempo (chained).
    - After last segment, pad/trim to match original_total_ms exactly.
    """
    # Ensure segments are sorted and monotonic
    segs = sorted(segments, key=lambda s: (s["start"], s["end"]))
    timeline = AudioSegment.silent(duration=0)
    cursor_ms = 0

    tmp_dir = app.config["UPLOAD_FOLDER"]

    for seg in segs:
        start_ms = max(0, int(round(seg["start"] * 1000)))
        end_ms = max(start_ms, int(round(seg["end"] * 1000)))
        target_dur = end_ms - start_ms
        text = (seg.get("text") or "").strip()

        # Gap before this segment
        if start_ms > cursor_ms:
            timeline += AudioSegment.silent(duration=(start_ms - cursor_ms))
            cursor_ms = start_ms

        if target_dur <= 0:
            continue

        if not text:
            # Empty segment: preserve timing as silence
            timeline += AudioSegment.silent(duration=target_dur)
            cursor_ms += target_dur
            continue

        try:
            # 1) TTS -> temp mp3
            seg_id = uuid.uuid4().hex
            tmp_mp3 = os.path.join(tmp_dir, f"seg_{seg_id}.mp3")
            gTTS(text=text, lang=tts_lang_code).save(tmp_mp3)

            # 2) Read to get actual duration D (ms)
            tts_audio = AudioSegment.from_file(tmp_mp3, format="mp3")
            D = max(1, len(tts_audio))  # guard min 1ms

            # 3) Export a wav to run precise atempo (mp3->wav for ffmpeg filter)
            tmp_in_wav = os.path.join(tmp_dir, f"in_{seg_id}.wav")
            tts_audio.export(tmp_in_wav, format="wav")

            # 4) Compute atempo chain to reach target_dur
            #    tempo = D/T  (so output duration ~ T)
            ratio = D / float(target_dur)
            atempo_chain = _build_atempo_chain(ratio)

            tmp_out_wav = os.path.join(tmp_dir, f"out_{seg_id}.wav")
            cmd = [
                "ffmpeg", "-y",
                "-i", tmp_in_wav,
                "-filter:a", atempo_chain,
                tmp_out_wav
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 5) Load processed audio, then micro pad/trim to exact target_dur
            processed = AudioSegment.from_file(tmp_out_wav, format="wav")

            if len(processed) > target_dur:
                processed = processed[:target_dur]
            elif len(processed) < target_dur:
                processed += AudioSegment.silent(duration=(target_dur - len(processed)))

            # 6) Place on timeline
            timeline += processed
            cursor_ms += target_dur

        except Exception as e:
            print("TTS/tempo error:", e)
            # keep timing even on error
            timeline += AudioSegment.silent(duration=target_dur)
            cursor_ms += target_dur
        finally:
            # cleanup temps
            for p in [locals().get("tmp_mp3"), locals().get("tmp_in_wav"), locals().get("tmp_out_wav")]:
                try:
                    if p and os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

    # Pad or trim to match the original audio track length
    if cursor_ms < original_total_ms:
        timeline += AudioSegment.silent(duration=(original_total_ms - cursor_ms))
    elif cursor_ms > original_total_ms:
        timeline = timeline[:original_total_ms]

    timeline.export(out_audio_path, format="mp3")
    return out_audio_path


# -----------------------
# Routes
# -----------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "video" not in request.files:
            return "No file part", 400
        f = request.files["video"]
        if f.filename == "":
            return "No selected file", 400
        # save uploaded file
        safe_name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        f.save(video_path)
        return redirect(url_for("player", filename=safe_name))
    return render_template("index.html", supported_langs=SUPPORTED_LANGS)

@app.route("/player/<path:filename>")
def player(filename):
    # Check that file exists
    video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(video_path):
        return "Video not found", 404
    # Pass supported languages to template
    return render_template("player.html", filename=filename, supported_langs=SUPPORTED_LANGS)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

@app.route("/translate", methods=["POST"])
def translate():
    """
    POST JSON expected:
    {
      "filename": "<uploaded file name>",
      "to": "hi"   # target language code from SUPPORTED_LANGS
    }
    Returns JSON with paths to generated .vtt and .mp3 (if created) and detected source language.
    """
    data = request.get_json()
    if not data or "filename" not in data or "to" not in data:
        return jsonify({"error": "filename and to required"}), 400

    filename = data["filename"]
    to_lang = data["to"]
    if to_lang not in SUPPORTED_LANGS:
        return jsonify({"error": "unsupported target language"}), 400

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(video_path):
        return jsonify({"error": "video not found"}), 404

    # Prepare working files
    wav_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.wav")
    extract_audio(video_path, wav_path)

    # Transcribe (Whisper)
    whisper_result = transcribe_with_whisper(wav_path)
    detected_lang = whisper_result.get("language", "unknown")
    segments = whisper_result.get("segments", [])
    normalized = [{"start": s["start"], "end": s["end"], "text": s.get("text", "")} for s in segments]

    # Translate segments
    translated_segments = translate_segment_texts(normalized, to_lang)

    # Save VTT for the target language
    vtt_name = f"{filename}.{to_lang}.vtt"
    vtt_path = os.path.join(app.config["UPLOAD_FOLDER"], vtt_name)
    segments_to_vtt(translated_segments, vtt_path)

    # Build aligned TTS on the real timeline and match final length to original audio
    tts_code = SUPPORTED_LANGS[to_lang]["ttscode"]
    mp3_name = f"{filename}.{to_lang}.mp3"
    mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_name)

    # Get original audio total length from the extracted wav
    orig_audio = AudioSegment.from_wav(wav_path)
    original_total_ms = len(orig_audio)

    tts_out = generate_aligned_tts_audio_timeline(
        translated_segments, tts_code, mp3_path, original_total_ms
    )

    # Return relative URLs so frontend can load them
    vtt_url = url_for("uploaded_file", filename=vtt_name)
    mp3_url = url_for("uploaded_file", filename=mp3_name) if tts_out else None

    return jsonify({
        "ok": True,
        "detected_source_language": detected_lang,
        "vtt": vtt_url,
        "mp3": mp3_url
    })

if __name__ == "__main__":
    app.run(debug=True)
