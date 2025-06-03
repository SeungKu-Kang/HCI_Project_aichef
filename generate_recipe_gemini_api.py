# generate_recipe_gemini_api.py

import os
import pyaudio        # type: ignore
from google.cloud import texttospeech
from google.oauth2 import service_account

# ——— Gemini(Generative AI) 로드 ———
try:
    import generativeai as genai
    if not hasattr(genai, "configure"):
        raise ImportError
except ImportError:
    try:
        import google.generativeai as genai
    except ImportError:
        genai = None

if genai:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        print("Error: GEMINI_API_KEY environment variable is not set.")
else:
    print("Error: Cannot find Gemini module. Run 'pip install google-generativeai' or 'pip install generativeai'.")

# ——— TTS 함수 (PCM → PyAudio) ———
def tts_speak(text: str):
    """
    Convert `text` to speech (LINEAR16 PCM) via Google TTS
    and play it immediately through PyAudio without writing to disk.
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.isfile(creds_path):
        print(f"[TTS Skip] Credentials missing or file not found at {creds_path}. Skipping TTS for: {text}")
        return

    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"[TTS Error] Failed to create TTS client: {e}")
        return

    # Build synthesis request
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    # Perform the Text-to-Speech request
    try:
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    except Exception as e:
        print(f"[TTS Error] Speech synthesis failed: {e}")
        return

    pcm_data = response.audio_content
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pa.get_format_from_width(2),  # 16-bit PCM
            channels=1,                          # mono
            rate=24000,                          # default sample rate for LINEAR16
            output=True
        )
        stream.write(pcm_data)
        stream.stop_stream()
        stream.close()
        pa.terminate()
    except Exception as e:
        print(f"[TTS Error] Audio playback failed: {e}")

# ——— Gemini 레시피 생성 함수 ———
def generate_recipe(dish_name: str) -> str:
    """
    Send an English-language prompt to Gemini to get a recipe for `dish_name`.
    Returns the raw text response.
    """
    if not genai:
        return "Error: Gemini module is not installed."
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY environment variable is not set."

    try:
        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")
        prompt = f'''
Please provide a detailed cooking recipe for the dish named "{dish_name}". 
Use the following format exactly, including headings:

【Dish Name】: [Insert dish name]

【Total Time】: [Insert estimated total time, or "Unknown" if not available]

【Ingredients】:
- [Ingredient 1 (quantity)]
- [Ingredient 2 (quantity)]
- ...

【Tools】:
- [Tool 1]
- [Tool 2]
- ...

【Steps】:
1. [First step detailed description]
2. [Second step detailed description]
3. ...

【Tips】 (optional; if none, write "No special tips"):
- [Any additional tip or caution]

Make sure not to repeat tool names inside the step descriptions. List ingredient quantities (e.g., "Pork (300g)").
'''
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Error] Failed to generate recipe: {e}")
        return f"Error during Gemini API call: {e}"
