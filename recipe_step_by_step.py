import re
from google.cloud import speech
from generate_recipe_gemini_api import generate_recipe, tts_speak
from stt_tts_test_code import MicrophoneStream, request_generator

# 레시피 문자열을 단계별 리스트로 분리
def get_recipe_steps(text: str):
    parts = re.split(r'\d+\.\s*', text)
    return [p.strip() for p in parts if p.strip()]

# 사용자가 "다음" 명령을 말할 때까지 대기하는 STT 함수
def listen_for_command():
    client = speech.SpeechClient()
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
    # 1) 어떤 요리 안내할지 물어보기
    prompt_text = "어떤 요리를 알려드릴까요?"
    print(prompt_text)
    tts_speak(prompt_text)
    dish = listen_for_command()

    # 2) Gemini API로 레시피 가져오기
    prompt = f"요리 레시피와 단계별 필요한 도구를 알려주세요: {dish}"
    print(prompt)
    recipe_text = generate_recipe(prompt)
    print(recipe_text)

    # 3) 단계별 분리
    steps = get_recipe_steps(recipe_text)
    if not steps:
        error_text = "죄송합니다. 레시피를 가져오지 못했습니다."
        print(error_text)
        tts_speak(error_text)
        return

    idx = 0
    # 4) 단계별 안내 루프
    while True:
        # 현재 단계 읽기
        step_text = f"{idx+1} 단계: {steps[idx]}"
        print(step_text)
        tts_speak(step_text)
        # 마지막 단계 확인
        if idx == len(steps) - 1:
            complete_text = "모든 단계가 완료되었습니다. 맛있게 드세요!"
            print(complete_text)
            tts_speak(complete_text)
            break

        # 다음 단계 전 대기
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
