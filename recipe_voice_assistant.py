# recipe_voice_assistant.py
import sys
print(f"실행 중인 파이썬 경로: {sys.executable}")
print(f"라이브러리 검색 경로: {sys.path}")

import os
import re
# generate_recipe_gemini_api.py에서 generate_recipe, tts_speak 임포트
from generate_recipe_gemini_api import generate_recipe, tts_speak 
# stt_tts_test_code.py에서 MicrophoneStream, request_generator 임포트
# MicrophoneStream과 request_generator는 stt_tts_test_code.py 에 있는 것을 사용
from stt_tts_test_code import MicrophoneStream, request_generator 
from google.cloud import speech, texttospeech

# --- tts_speak_en, speak_bilingual, listen_for_trigger 함수는 기존 코드 유지 ---
# (tts_speak_en 함수는 generate_recipe_gemini_api.py의 tts_speak을 참고하여 유사하게 구성)
def tts_speak_en(text: str): #
    """영어 전용 TTS"""
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("오류: GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다. 영어 TTS를 건너<0xEB><0x9A><0xBSkip>니다.")
        print(f"[TTS-EN-Skip] {text}")
        return

    client = texttospeech.TextToSpeechClient() #
    synthesis_input = texttospeech.SynthesisInput(text=text) #
    voice = texttospeech.VoiceSelectionParams( #
        language_code="en-US", #
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL #
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16) #
    resp = client.synthesize_speech( #
        input=synthesis_input, voice=voice, audio_config=audio_config #
    )
    output_file = "recipe_reply_en.wav" # 영어 응답 파일 분리
    with open(output_file, 'wb') as f: #
        f.write(resp.audio_content) #

    print(f"[TTS-EN] {text}")

    if os.name == 'posix': #
        try:
            os.system(f"afplay {output_file}")  # macOS
        except Exception:
            os.system(f"aplay {output_file}")   # Linux
    elif os.name == 'nt': #
        # os.startfile(output_file) # # 필요시 주석 해제
        print(f"Windows에서는 '{output_file}' 파일을 직접 실행하여 들어주세요.")


def speak_bilingual(ko_text: str, en_text: str): #
    """한글 → 영어 TTS 순서대로 실행"""
    tts_speak(ko_text) #
    # 영어 음성이 필요할 때만 tts_speak_en 호출 (예: 사용자가 영어로 상호작용 선택 시)
    # 현재는 한국어 위주로 진행하므로, 영어 TTS는 선택적으로 호출하도록 아래 로직에서 제어
    # tts_speak_en(en_text)


def listen_for_trigger(timeout_sec: int = 15) -> str: # listen_for_command와 유사
    # 기존 listen_for_trigger 함수 로직 사용 (stt_tts_test_code.py의 MicrophoneStream 사용)
    # 이 함수는 이미 한/영 동시 인식을 위한 alternative_language_codes를 포함하고 있음
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("오류: GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다. STT를 건너<0xEB><0x9A><0xBSkip>니다.")
        return "테스트명령" # 테스트용 기본 반환값 또는 빈 문자열

    client = speech.SpeechClient() #
    config = speech.RecognitionConfig( #
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, #
        sample_rate_hertz=16000, # # generate_recipe_gemini_api.py 와 일치시키거나 config 파일로 관리
        language_code="ko-KR", #
        alternative_language_codes=["en-US"], #
    )
    streaming_config = speech.StreamingRecognitionConfig( #
        config=config, interim_results=False #
    )

    mic = MicrophoneStream() # stt_tts_test_code.py에서 임포트
    mic.start() #
    transcript = ""
    
    # request_generator는 stt_tts_test_code.py에서 임포트
    # 이 부분은 timeout 로직이 명시적으로 없어, 사용자가 말을 할 때까지 계속 기다리거나 스트림이 종료될 때까지 대기합니다.
    # 실제 timeout 처리는 더 복잡한 로직 (별도 스레드 타이머 등)이 필요할 수 있습니다.
    # 여기서는 첫 번째 최종 응답을 받으면 종료하는 단순 형태로 가정합니다.
    print("명령어 입력 대기 중...")
    try:
        responses = client.streaming_recognize( #
            streaming_config, #
            request_generator() # stt_tts_test_code.py에서 임포트
        )
        for resp in responses: #
            if resp.results and resp.results[0].is_final: #
                transcript = resp.results[0].alternatives[0].transcript.lower().strip() #
                print(f"[STT] 인식: {transcript}")
                break 
    except Exception as e: #
        print(f"[STT Error] {e}") #
    finally:
        mic.stop() #
        # audio_utils.py의 listen_for_command 처럼 audio_queue를 비워주는 로직 추가 가능
    return transcript


# --- 기존 get_recipe_steps 함수는 새로운 파서로 대체되므로 주석 처리 또는 삭제 ---
# def get_recipe_steps(recipe_text: str):
#     parts = re.split(r'\d+\.\s*', recipe_text)
#     return [p.strip() for p in parts if p.strip()]

# +++ 새로운 구조화된 레시피 파싱 함수 +++
def parse_structured_recipe(recipe_text: str) -> dict:
    parsed_data = {
        "dish_name": "정보 없음",
        "total_time": "정보 없음",
        "ingredients": [],
        "tools": [],
        "steps": [],
        "tips": "특별한 팁 없음"
    }
    if not recipe_text or recipe_text.startswith("오류:") or recipe_text.startswith("Gemini API 호출 중 오류"):
        print(f"[Parser] 유효하지 않은 레시피 텍스트: {recipe_text}")
        return parsed_data

    try:
        # 각 섹션별로 텍스트 추출 (정규표현식 사용)
        dish_name_match = re.search(r"\*\*요리 이름:\*\*\s*(.+?)\s*(?=\n\*\*|$)", recipe_text, re.IGNORECASE)
        if dish_name_match:
            parsed_data["dish_name"] = dish_name_match.group(1).strip()

        total_time_match = re.search(r"\*\*전체 소요 시간:\*\*\s*(.+?)\s*(?=\n\*\*|$)", recipe_text, re.IGNORECASE)
        if total_time_match:
            parsed_data["total_time"] = total_time_match.group(1).strip()
        
        ingredients_block_match = re.search(r"\*\*재료:\*\*\s*\n(.*?)(?=\n\*\*필요한 도구:\*\*|\n\*\*만드는 단계:\*\*|\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if ingredients_block_match:
            ingredients_text = ingredients_block_match.group(1).strip()
            parsed_data["ingredients"] = [line.strip().lstrip('- ') for line in ingredients_text.split('\n') if line.strip().lstrip('- ')]

        tools_block_match = re.search(r"\*\*필요한 도구:\*\*\s*\n(.*?)(?=\n\*\*만드는 단계:\*\*|\n\*\*팁:\*\*|\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if tools_block_match:
            tools_text = tools_block_match.group(1).strip()
            parsed_data["tools"] = [line.strip().lstrip('- ') for line in tools_text.split('\n') if line.strip().lstrip('- ')]

        steps_block_match = re.search(r"\*\*만드는 단계:\*\*\s*\n(.*?)(?=\n\*\*팁:\*\*|\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if steps_block_match:
            steps_text = steps_block_match.group(1).strip()
            # 숫자. 로 시작하고, 내용이 있는 라인만 추출
            raw_steps = [line.strip() for line in steps_text.split('\n') if re.match(r"^\d+\.\s*\S+", line.strip())]
            parsed_data["steps"] = [re.sub(r"^\d+\.\s*", "", step).strip() for step in raw_steps]
        
        tips_block_match = re.search(r"\*\*팁:\*\*\s*\n(.*?)(?=\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if tips_block_match:
            tips_text = tips_block_match.group(1).strip()
            if tips_text : parsed_data["tips"] = tips_text
            
    except Exception as e:
        print(f"[Parser Error] 레시피 파싱 중 오류: {e}")
        # 오류 발생 시 디버깅을 위해 원본 텍스트 일부 출력
        print(f"원본 텍스트 (일부): {recipe_text[:500]}")

    # print(f"파싱된 데이터: {parsed_data}") # 디버깅용 출력
    return parsed_data


# --- 인터랙티브 안내 루프 수정 ---
def run_step_by_step():
    # 1) 메뉴 선택
    tts_speak("안녕하세요! 어떤 요리를 알려드릴까요?") # speak_bilingual 대신 한국어만 사용
    dish_query = listen_for_trigger()

    if not dish_query or dish_query == "테스트명령": # STT 실패 또는 기본값일 경우
        tts_speak("요리 이름을 듣지 못했어요. 다음에 다시 시도해주세요.")
        return

    tts_speak(f"{dish_query} 레시피를 찾고 있어요. 잠시만 기다려주세요.")

    # 2) 레시피 생성 (generate_recipe_gemini_api.py의 수정된 함수 사용)
    full_recipe_text = generate_recipe(dish_query) # 이제 dish_name만 전달

    if not full_recipe_text or full_recipe_text.startswith("오류:") or full_recipe_text.startswith("Gemini API 호출 중 오류"):
        tts_speak(f"죄송합니다. {dish_query} 레시피를 가져오지 못했습니다. {full_recipe_text}")
        return

    # 3) 새로운 파서로 레시피 정보 추출
    recipe_data = parse_structured_recipe(full_recipe_text)
    
    # API 응답에서 요리 이름이 있으면 사용, 없으면 사용자 입력 사용
    # dish_name_to_speak = recipe_data.get("dish_name", dish_query) 
    # if dish_name_to_speak == "정보 없음": dish_name_to_speak = dish_query
    dish_name_to_speak = recipe_data["dish_name"] if recipe_data["dish_name"] != "정보 없음" else dish_query


    ingredients = recipe_data.get("ingredients", [])
    tools = recipe_data.get("tools", [])
    steps = recipe_data.get("steps", [])

    if not steps: # 단계 정보가 없으면 진행 불가
        tts_speak(f"죄송합니다. '{dish_name_to_speak}' 레시피의 단계 정보를 제대로 분석하지 못했어요.")
        # print(f"전체 응답 내용:\n{full_recipe_text}") # 디버깅 필요시 전체 응답 출력
        return

    # 4) 전체 재료 및 도구 일괄 안내
    tts_speak(f"{dish_name_to_speak} 요리 안내를 시작하겠습니다.")
    if ingredients:
        ing_list_str = ", ".join(ingredients)
        tts_speak(f"먼저, 필요한 전체 재료는 {ing_list_str} 입니다.")
    else:
        tts_speak("재료 정보가 명확하지 않네요.")

    if tools:
        tool_list_str = ", ".join(tools)
        tts_speak(f"그리고 필요한 도구는 {tool_list_str} 입니다.")
    else:
        tts_speak("도구 정보가 명확하지 않네요.")

    # 요리 시작 여부 확인
    tts_speak("모든 재료와 도구가 준비되셨으면, '시작', '준비됐어', 또는 '다음'이라고 말씀해주세요.")
    
    ready_to_start = False
    while not ready_to_start:
        cmd = listen_for_trigger(timeout_sec=20)
        if any(k in cmd for k in ["시작", "준비 됐어", "준비됐어", "다음", "네", "응", "next", "start", "yes", "ok"]):
            ready_to_start = True
        elif not cmd or cmd == "테스트명령": # 타임아웃 또는 STT 실패
             tts_speak("계속하려면 '시작' 또는 '다음'이라고 말씀해주세요.")
        else:
            tts_speak(f"'{cmd}'라고 말씀하신 것 같아요. 요리를 시작하려면 '시작' 또는 '다음'이라고 해주세요.")
    
    # 5) 첫 단계 안내
    current_step_idx = 0
    tts_speak(f"좋아요! 첫 번째 단계입니다. {steps[current_step_idx]}")

    # 6) 사용자 명령어 기반 단계 진행 루프
    while current_step_idx < len(steps):
        # 다음 사용자 입력을 받기 전에 안내 메시지
        tts_speak("다음 행동을 말씀해주세요: '다음 단계', '이전 단계', '다시 알려줘', '재료 확인', '도구 확인', 또는 '요리 종료'.")
        cmd = listen_for_trigger(timeout_sec=25) # 명령어 대기 시간 약간 늘림

        if not cmd or cmd == "테스트명령": # STT 실패 또는 타임아웃
            tts_speak("명령을 듣지 못했어요. 어떻게 할까요?")
            continue

        # 명령어 처리 로직
        if any(k in cmd for k in ["다음 단계", "다음", "넥스트", "next step", "next"]):
            current_step_idx += 1
            if current_step_idx < len(steps):
                tts_speak(f"{current_step_idx + 1} 단계입니다. {steps[current_step_idx]}")
            else:
                tts_speak("축하합니다! 모든 단계가 완료되었습니다. 맛있게 드세요!")
                if recipe_data.get("tips") and recipe_data["tips"] != "특별한 팁 없음":
                    tts_speak(f"마지막으로, 유용한 팁입니다: {recipe_data['tips']}")
                break 
        elif any(k in cmd for k in ["다시 알려줘", "반복", "리핏", "repeat", "again", "뭐라고"]):
            tts_speak(f"네, 다시 알려드릴게요. 현재 {current_step_idx + 1} 단계는 {steps[current_step_idx]} 입니다.")
        elif any(k in cmd for k in ["이전 단계", "이전", "프리비어스", "previous step", "previous"]):
            if current_step_idx > 0:
                current_step_idx -= 1
                tts_speak(f"{current_step_idx + 1} 단계로 돌아갑니다. {steps[current_step_idx]}")
            else:
                tts_speak("이미 첫 번째 단계입니다. 이전 단계로 돌아갈 수 없어요.")
        elif any(k in cmd for k in ["재료 확인", "재료 목록", "재료 뭐였지", "ingredients"]):
            if ingredients:
                ing_list_str = ", ".join(ingredients)
                tts_speak(f"이 요리에 사용된 전체 재료는 {ing_list_str} 입니다.")
            else:
                tts_speak("죄송하지만, 현재 재료 정보를 다시 불러올 수 없네요.")
        elif any(k in cmd for k in ["도구 확인", "도구 목록", "도구 뭐였지", "tools"]):
            if tools:
                tool_list_str = ", ".join(tools)
                tts_speak(f"이 요리에 사용된 전체 도구는 {tool_list_str} 입니다.")
            else:
                tts_speak("죄송하지만, 현재 도구 정보를 다시 불러올 수 없네요.")
        elif any(k in cmd for k in ["현재 단계", "지금 몇 단계", "what step"]):
             tts_speak(f"지금은 {current_step_idx + 1} 단계이고, 내용은 다음과 같습니다. {steps[current_step_idx]}")
        elif any(k in cmd for k in ["요리 종료", "그만할래", "종료", "스탑", "stop", "exit"]):
            tts_speak("알겠습니다. 요리 안내를 종료합니다. 이용해주셔서 감사합니다!")
            break
        else:
            tts_speak(f"죄송해요. '{cmd}'라고 말씀하신 것 같아요. 제가 이해할 수 있는 명령으로 다시 말씀해주시겠어요?")

if __name__ == "__main__":
    # 환경 변수 존재 여부 확인
    gemini_key = os.getenv("GEMINI_API_KEY")
    gcp_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not gemini_key:
        print("오류: 환경변수 'GEMINI_API_KEY'가 설정되지 않았습니다.")
    if not gcp_creds:
        print("오류: 환경변수 'GOOGLE_APPLICATION_CREDENTIALS'가 설정되지 않았습니다.")
    
    if gemini_key and gcp_creds:
        # PyAudio 관련 체크는 stt_tts_test_code.py 또는 audio_utils.py 에서 이미 처리될 수 있으므로
        # 여기서는 생략하거나, MicrophoneStream 객체 생성 시 발생하는 예외를 잡는 방식으로 처리 가능
        try:
            # 간단한 PyAudio 라이브러리 확인
            import pyaudio # type: ignore
            p = pyaudio.PyAudio()
            p.terminate()
            print("PyAudio 확인 완료.")
            run_step_by_step()
        except ImportError:
            print("오류: PyAudio 라이브러리를 찾을 수 없습니다. 설치가 필요합니다.")
        except Exception as e_main:
            if "PortAudio" in str(e_main) or "No Default Input Device Available" in str(e_main) :
                 print(f"오디오 장치 오류 또는 PortAudio 라이브러리 문제: {e_main}")
                 print("마이크가 연결되어 있는지, PortAudio가 올바르게 설치되었는지 확인해주세요.")
                 print("Linux: sudo apt-get install portaudio19-dev python3-pyaudio")
                 print("macOS: brew install portaudio && pip install pyaudio")
            else:
                print(f"실행 중 예기치 않은 오류 발생: {e_main}")
    else:
        print("필수 환경 변수가 설정되지 않아 프로그램을 실행할 수 없습니다.")