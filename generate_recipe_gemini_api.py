# generate_recipe_gemini_api.py

import os
import queue # generate_recipe_gemini_api.py 에는 없었으나, 다른 파일과의 일관성 또는 확장성 위해 추가 고려 가능
import pyaudio # type: ignore # generate_recipe_gemini_api.py 에는 없었으나, 다른 파일과의 일관성 또는 확장성 위해 추가 고려 가능
from google.cloud import speech, texttospeech
from google import generativeai as genai #

# Gemini Developer API 클라이언트 설정
# 환경 변수로 GEMINI_API_KEY 설정 필요
if os.getenv("GEMINI_API_KEY"): # API 키 존재 확인 후 configure
    genai.configure(api_key=os.getenv("GEMINI_API_KEY")) #
else:
    print("오류: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

# STT/TTS 설정 상수 (recipe_voice_assistant.py 와 중복될 수 있으나, 이 파일 단독 실행 가능성을 위해 유지 또는 config 파일로 분리)
RATE = 16000 #
CHUNK = int(RATE / 10)  # 100ms
FORMAT = pyaudio.paInt16 # type: ignore #
CHANNELS = 1 #

# audio_queue = queue.Queue() # 이 파일에서 직접 MicrophoneStream을 사용하지 않으면 불필요

# 마이크 스트림 클래스 (recipe_voice_assistant.py에서 stt_tts_test_code 임포트하므로 여기선 제거 또는 주석 처리)
# class MicrophoneStream: ...

# STT 요청 생성기 (recipe_voice_assistant.py에서 stt_tts_test_code 임포트하므로 여기선 제거 또는 주석 처리)
# def request_generator(): ...

# Gemini 호출 함수
def generate_recipe(dish_name: str) -> str: # 입력 인자를 dish_name으로 명확히 함
    if not os.getenv("GEMINI_API_KEY"):
        return "오류: Gemini API 키가 설정되지 않았습니다."

    model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest") #
    
    # Gemini API가 일관된 형식으로 응답하도록 프롬프트 수정
    prompt = f"""
    요리 레시피를 상세히 알려주세요. 음식 이름은 "{dish_name}"입니다.
    반드시 다음 형식에 맞춰서 응답해주세요. 각 섹션 제목(예: **요리 이름:**)은 그대로 사용해주세요:

    **요리 이름:** [여기에 요리 이름]

    **전체 소요 시간:** [여기에 예상 소요 시간, 정보 없으면 "정보 없음"으로 표시]

    **재료:**
    - [재료 1 (양)]
    - [재료 2 (양)]
    - [기타 재료...]

    **필요한 도구:**
    - [도구 1]
    - [도구 2]
    - [기타 도구...]

    **만드는 단계:**
    1. [첫 번째 단계 상세 설명]
    2. [두 번째 단계 상세 설명]
    3. [기타 단계들...]

    **팁:** (선택 사항, 없으면 이 섹션 생략 가능 또는 "특별한 팁 없음"으로 표시)
    - [추가적인 팁이나 주의사항]

    만드는 단계 설명 시에는 도구 이름을 반복하지 말고, '필요한 도구' 섹션에 모든 도구를 명시해주세요.
    재료에는 필요한 양도 함께 표시해주세요 (예: 돼지고기 (300g)).
    """
    
    try:
        # chat = model.start_chat(history=[]) # # 단일 요청이므로 generate_content 사용 가능
        # response = chat.send_message(prompt)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Error] 레시피 생성 중 오류 발생: {e}")
        return f"Gemini API 호출 중 오류가 발생했습니다: {e}"


# TTS 호출 함수 (recipe_voice_assistant.py에도 tts_speak_en 과 speak_bilingual이 있으므로, 여기서는 한국어 TTS만 남기거나, recipe_voice_assistant.py의 것을 사용하도록 통일)
def tts_speak(text: str): #
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("오류: GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다. TTS를 건너<0xEB><0x9A><0xBSkip>니다.")
        print(f"[TTS-Skip] {text}")
        return

    tts_client = texttospeech.TextToSpeechClient() #
    synthesis_input = texttospeech.SynthesisInput(text=text) #
    voice = texttospeech.VoiceSelectionParams( #
        language_code="ko-KR", #
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL #
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16) #
    resp = tts_client.synthesize_speech( #
        input=synthesis_input, #
        voice=voice, #
        audio_config=audio_config #
    )
    output_file = "recipe_reply.wav" #
    with open(output_file, 'wb') as f: #
        f.write(resp.audio_content) #
    
    print(f"[TTS] {text}") # 콘솔에도 TTS 내용 출력

    if os.name == 'posix': #
        if os.uname().sysname == 'Darwin': #
            os.system(f"afplay {output_file}") #
        else: #
            os.system(f"aplay {output_file}") #
    elif os.name == 'nt': #
        print(f"Windows에서는 '{output_file}' 파일을 직접 실행하여 들어주세요.") #
        try:
            os.startfile(output_file) #
        except AttributeError: #
            print("Windows에서 오디오 파일을 자동 재생하려면 추가 설정이 필요할 수 있습니다.") #

# 메인 함수 (이 파일은 주로 라이브러리처럼 사용되므로, main 부분은 테스트용으로 남기거나 제거)
# if __name__ == '__main__':
#     # 간단한 테스트 로직
#     test_dish = "김치찌개"
#     print(f"{test_dish} 레시피 요청 테스트:")
#     recipe_response = generate_recipe(test_dish)
#     print("\n[Gemini 응답]:")
#     print(recipe_response)
#     if not recipe_response.startswith("오류:") and recipe_response: # API 키 오류 등이 아닐 때만 TTS
#         tts_speak(f"{test_dish} 레시피입니다. 자세한 내용은 콘솔을 확인해주세요.") # 전체 레시피를 읽으면 너무 길다.