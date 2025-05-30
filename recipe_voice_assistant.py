import os
import re
from generate_recipe_gemini_api import generate_recipe, tts_speak
from stt_tts_test_code import MicrophoneStream, request_generator
from google.cloud import speech, texttospeech

# ——— 한글→영어 이중 TTS 함수 ———

def tts_speak_en(text: str):
    """영어 전용 TTS"""
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    resp = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    output_file = "recipe_reply.wav"
    with open(output_file, 'wb') as f:
        f.write(resp.audio_content)

    # 오디오 재생
    if os.name == 'posix':
        try:
            os.system(f"afplay {output_file}")  # macOS
        except Exception:
            os.system(f"aplay {output_file}")   # Linux
    elif os.name == 'nt':
        os.startfile(output_file)


def speak_bilingual(ko_text: str, en_text: str):
    """한글 → 영어 TTS 순서대로 실행"""
    tts_speak(ko_text)      # 한글 안내
    tts_speak_en(en_text)   # 영어 안내

# ——— STT 트리거 대기 함수 (한·영 인식) ———

def listen_for_trigger(timeout_sec: int = 10) -> str:
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="ko-KR",
        alternative_language_codes=["en-US"],
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=False
    )

    mic = MicrophoneStream()
    mic.start()
    transcript = ""
    try:
        responses = client.streaming_recognize(
            streaming_config,
            request_generator()
        )
        for resp in responses:
            if resp.results and resp.results[0].is_final:
                transcript = resp.results[0].alternatives[0].transcript.lower()
                break
    except Exception as e:
        print(f"[STT Error] {e}")
    finally:
        mic.stop()
    return transcript

# ——— 레시피 단계 분리 ———

def get_recipe_steps(recipe_text: str):
    parts = re.split(r'\d+\.\s*', recipe_text)
    return [p.strip() for p in parts if p.strip()]

# ——— 인터랙티브 안내 루프 ———

def run_step_by_step():
    # 1) 메뉴 선택
    speak_bilingual(
        "어떤 요리를 알려드릴까요?",
        "What dish would you like me to guide you through?"
    )
    dish = listen_for_trigger()

    # 2) 레시피 생성
    prompt = f"요리 레시피와 단계별 필요한 도구를 알려주세요: {dish}"
    full_recipe = generate_recipe(prompt)

    # 3) 단계 분리
    steps = get_recipe_steps(full_recipe)
    if not steps:
        speak_bilingual(
            "죄송합니다. 레시피를 가져오지 못했어요.",
            "Sorry, I couldn't retrieve the recipe."
        )
        return

    # 4) 첫 단계 안내
    speak_bilingual(
        f"첫 번째 단계입니다. {steps[0]}",
        f"This is the first step: {steps[0]}"
    )
    idx = 0

    # 5) “다음 단계/next step” 대기 & 처리
    while idx < len(steps) - 1:
        speak_bilingual(
            "다음 단계를 말씀해주세요.",
            "Please say ‘next step’."
        )
        cmd = listen_for_trigger(timeout_sec=15)

        if any(k in cmd for k in ["다음 단계", "다음", "next step", "next"]):
            idx += 1
            speak_bilingual(
                f"{idx+1} 단계입니다. {steps[idx]}",
                f"This is step {idx+1}: {steps[idx]}"
            )

        elif any(k in cmd for k in ["반복", "다시", "repeat", "again"]):
            speak_bilingual(
                f"다시 알려드릴게요. {steps[idx]}",
                f"I'll repeat it: {steps[idx]}"
            )

        else:
            speak_bilingual(
                "죄송해요. ‘다음 단계’ 혹은 ‘next step’이라고 말씀해 주세요.",
                "I'm sorry. Please say ‘next step’."
            )

    # 6) 완료 안내
    speak_bilingual(
        "모든 단계가 완료되었습니다. 맛있게 드세요!",
        "All steps are completed. Enjoy your meal!"
    )

if __name__ == "__main__":
    run_step_by_step()
