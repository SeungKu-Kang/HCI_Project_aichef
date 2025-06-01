# generate_recipe_gemini_api.py

import os
import queue
import pyaudio        # type: ignore
import tempfile
import threading
import wave
from google.cloud import speech, texttospeech
from google.oauth2 import service_account

# ——— Gemini(Generative AI) 라이브러리 로드 ———
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
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("오류: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
else:
    print("오류: Gemini 모듈을 찾을 수 없습니다. 'pip install google-generativeai' 또는 'pip install generativeai'를 실행하세요.")

# STT/TTS 관련 상수
RATE = 16000
CHUNK = int(RATE / 10)
FORMAT = pyaudio.paInt16
CHANNELS = 1

# ——— TTS 호출 (PCM 바이트 → PyAudio 재생) ———
def tts_speak(text: str):
    """
    Google Cloud Text-to-Speech로 'text'를 합성한 뒤,
    생성된 PCM(LINEAR16) 바이트를 PyAudio로 바로 재생합니다.
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.isfile(creds_path):
        print("오류: GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 없거나, 경로가 잘못되었습니다. TTS 건너뜁니다.")
        print(f"[TTS-Skip] {text}")
        return

    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"[TTS Error] TTS 클라이언트 생성 실패: {e}")
        return

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
    except Exception as e:
        print(f"[TTS Error] 음성 합성 실패: {e}")
        return

    pcm_data = response.audio_content
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pa.get_format_from_width(2),
            channels=1,
            rate=24000,
            output=True
        )
        stream.write(pcm_data)
        stream.stop_stream()
        stream.close()
        pa.terminate()
    except Exception as e:
        print(f"[TTS Error] 오디오 재생 실패: {e}")

# ——— Gemini 레시피 생성 함수 ———
def generate_recipe(dish_name: str) -> str:
    """
    Gemini 모델에 프롬프트를 보내어 'dish_name' 레시피를 반환합니다.
    """
    if not genai:
        return "오류: Gemini 모듈이 설치되지 않았습니다."
    if not os.getenv("GEMINI_API_KEY"):
        return "오류: Gemini API 키가 설정되지 않았습니다."

    try:
        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")
        prompt = f'''
요리 레시피를 상세히 알려주세요. 음식 이름은 "{dish_name}"입니다.
반드시 아래 형식에 맞춰 응답해 주세요:

**요리 이름:** [요리 이름]

**전체 소요 시간:** [예: 30분] (없으면 "정보 없음")

**재료:**
- [재료 1 (양)]
- [재료 2 (양)]
- …

**필요한 도구:**
- [도구 1]
- [도구 2]
- …

**만드는 단계:**
1. [첫 번째 단계 상세 설명]
2. [두 번째 단계 상세 설명]
…

**팁:** (없으면 "특별한 팁 없음")
- [팁 내용]
'''
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Error] 레시피 생성 실패: {e}")
        return f"Gemini API 호출 중 오류가 발생했습니다: {e}"
