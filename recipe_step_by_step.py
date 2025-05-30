import os
import re
from google.oauth2 import service_account
from google.cloud import speech, texttospeech
from generate_recipe_gemini_api import generate_recipe, tts_speak
from stt_tts_test_code import MicrophoneStream, request_generator

# ——— 자격 증명 로드 ———
def load_credentials():
    # JSON 키 파일 경로는 반드시 환경 변수에만 설정
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("[Error] 환경 변수 GOOGLE_APPLICATION_CREDENTIALS가 설정되지 않았습니다.")
        print("키 파일의 절대 경로를 환경 변수에 지정해주세요.")
        exit(1)
    if not os.path.isfile(cred_path):
        print(f"[Error] Credential file not found at {cred_path}")
        print("환경 변수가 올바른지, 그리고 해당 경로에 파일이 존재하는지 확인해주세요.")
        exit(1)
    return service_account.Credentials.from_service_account_file(cred_path)

# 전역 자격증명 객체
CREDS = load_credentials()

# 레시피 문자열을 단계별 리스트로 분리
def get_recipe_steps(text: str):
    parts = re.split(r'\d+\.\s*', text)
    return [p.strip() for p in parts if p.strip()]

# 사용자가 "다음" 명령을 말할 때까지 대기하는 STT 함수
def listen_for_command():
    client = speech.SpeechClient(credentials=CREDS)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="ko-KR",
        alternative_language_codes=["en-US"]
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=False)

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

# 메인 인터랙티브 함수
def main():
    prompt_text = "어떤 요리를 알려드릴까요?"
    print(prompt_text)
    tts_speak(prompt_text)
    dish = listen_for_command()

    prompt = f"요리 레시피와 단계별 필요한 도구를 알려주세요: {dish}"
    print(prompt)
    recipe_text = generate_recipe(prompt)
    print(recipe_text)

    steps = get_recipe_steps(recipe_text)
    if not steps:
        error_text = "죄송합니다. 레시피를 가져오지 못했습니다."
        print(error_text)
        tts_speak(error_text)
        return

    idx = 0
    while True:
        step_text = f"{idx+1} 단계: {steps[idx]}"
        print(step_text)
        tts_speak(step_text)
        if idx == len(steps) - 1:
            complete_text = "모든 단계가 완료되었습니다. 맛있게 드세요!"
            print(complete_text)
            tts_speak(complete_text)
            break

        while True:
            next_prompt = "다음이라고 말씀해 주세요."
            print(next_prompt)
            tts_speak(next_prompt)
            cmd = listen_for_command()
            if any(k in cmd for k in ["다음 단계", "다음", "next step", "next"]):
                idx += 1
                break
            else:
                retry_text = "죄송합니다. '다음'이라고 다시 말씀해 주세요."
                print(retry_text)
                tts_speak(retry_text)

if __name__ == "__main__":
    main()
