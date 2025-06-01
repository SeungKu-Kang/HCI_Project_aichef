# recipe_voice_assistant.py

import os
import re
import sys
from google.oauth2 import service_account
from google.cloud import speech, texttospeech
from generate_recipe_gemini_api import generate_recipe, tts_speak
from stt_tts_test_code import MicrophoneStream, request_generator

# ─── 자격 증명 로드 ───
def load_credentials():
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("[Error] 환경 변수 GOOGLE_APPLICATION_CREDENTIALS가 설정되지 않았습니다.")
        print("키 파일 절대 경로를 환경 변수에 지정해 주세요.")
        sys.exit(1)
    if not os.path.isfile(cred_path):
        print(f"[Error] Credential file not found at {cred_path}")
        print("환경 변수 경로가 올바른지, 파일이 존재하는지 확인해 주세요.")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(cred_path)

CREDS = load_credentials()

# ─── STT 듣기 함수 ───
def listen_for_trigger(timeout_sec: int = 15) -> str:
    """
    마이크로부터 음성을 받아 '다음', '이전', 또는 요리 이름 등을 텍스트로 반환합니다.
    """
    client = speech.SpeechClient(credentials=CREDS)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="ko-KR",
        alternative_language_codes=["en-US"],
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=False)

    mic = MicrophoneStream()
    mic.start()
    transcript = ""

    print("[STT] 명령어 입력 대기 중...")

    try:
        for resp in client.streaming_recognize(
            streaming_config,
            request_generator()
        ):
            if resp.results and resp.results[0].is_final:
                transcript = resp.results[0].alternatives[0].transcript.lower().strip()
                print(f"[STT] 인식: {transcript}")
                break
    except Exception as e:
        print(f"[STT Error] {e}")
    finally:
        mic.stop()

    return transcript

# ─── 사용자 발화를 바탕으로 요리 이름 추출 함수 ───
def extract_dish_name(query: str) -> str:
    """
    예: "김치찜 레시피를 알려줘" -> "김치찜"
    """
    # 한글 '레시피' 앞의 단어를 추출
    if not query:
        return ''
    # 문장에서 '레시피' 단어가 포함되면, 그 이전 부분을 요리 이름으로 간주
    if '레시피' in query:
        name_part = query.split('레시피')[0].strip()
        # '를', '을', '을' 같이 조사 제거
        name_part = re.sub(r'(을|를|을|를)?$', '', name_part).strip()
        return name_part
    # 영어 'recipe' 단어 처리
    if 'recipe' in query:
        name_part = query.split('recipe')[0].strip()
        return name_part
    # 위 키워드가 없으면 전체 문장을 그대로 반환
    return query

# ─── 레시피 구조화 파싱 함수 ───
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
        dish_name_match = re.search(r"\*\*요리 이름:\*\*\s*(.+?)\s*(?=\n\*\*|$)", recipe_text, re.IGNORECASE)
        if dish_name_match:
            parsed_data["dish_name"] = dish_name_match.group(1).strip()

        total_time_match = re.search(r"\*\*전체 소요 시간:\*\*\s*(.+?)\s*(?=\n\*\*|$)", recipe_text, re.IGNORECASE)
        if total_time_match:
            parsed_data["total_time"] = total_time_match.group(1).strip()

        ingredients_block_match = re.search(
            r"\*\*재료:\*\*\s*\n(.*?)(?=\n\*\*필요한 도구:\*\*|\n\*\*만드는 단계:\*\*|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if ingredients_block_match:
            ing_text = ingredients_block_match.group(1).strip()
            parsed_data["ingredients"] = [
                line.strip().lstrip('- ').strip()
                for line in ing_text.split('\n') if line.strip().lstrip('- ').strip()
            ]

        tools_block_match = re.search(
            r"\*\*필요한 도구:\*\*\s*\n(.*?)(?=\n\*\*만드는 단계:\*\*|\n\*\*팁:\*\*|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if tools_block_match:
            tools_text = tools_block_match.group(1).strip()
            parsed_data["tools"] = [
                line.strip().lstrip('- ').strip()
                for line in tools_text.split('\n') if line.strip().lstrip('- ').strip()
            ]

        steps_block_match = re.search(
            r"\*\*만드는 단계:\*\*\s*\n(.*?)(?=\n\*\*팁:\*\*|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if steps_block_match:
            steps_text = steps_block_match.group(1).strip()
            raw_steps = [
                line.strip() for line in steps_text.split('\n')
                if re.match(r"^\d+\.\s*\S+", line.strip())
            ]
            parsed_data["steps"] = [re.sub(r"^\d+\.\s*", "", step).strip() for step in raw_steps]

        tips_block_match = re.search(r"\*\*팁:\*\*\s*\n(.*?)(?=\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if tips_block_match:
            tips_text = tips_block_match.group(1).strip()
            if tips_text:
                parsed_data["tips"] = tips_text

    except Exception as e:
        print(f"[Parser Error] 레시피 파싱 중 오류: {e}")
        print(f"원본 텍스트(일부): {recipe_text[:300]}")

    return parsed_data

# ─── 메인: 단계별 음성 안내 루프 ───
def run_step_by_step():
    # 1) 사용자에게 메뉴 물어보기
    prompt_text = "안녕하세요! 어떤 요리를 알려드릴까요?"
    print(prompt_text)
    tts_speak(prompt_text)

    raw_query = listen_for_trigger()
    # 사용자가 말한 문장에서 요리 이름만 추출
    dish_query = extract_dish_name(raw_query)
    print(f"[Dish Query] 원문: '{raw_query}' → 추출된 요리: '{dish_query}'")

    if not dish_query:
        tts_speak("요리 이름을 듣지 못했어요. 다음에 다시 시도해주세요.")
        return

    tts_speak(f"{dish_query} 레시피를 찾고 있어요. 잠시만 기다려주세요.")

    # 2) Gemini API로 레시피 가져오기
    full_recipe_text = generate_recipe(dish_query)

    if not full_recipe_text or full_recipe_text.startswith("오류:") or full_recipe_text.startswith("Gemini API 호출 중 오류"):
        tts_speak(f"죄송합니다. {dish_query} 레시피를 가져오지 못했습니다. {full_recipe_text}")
        return

    # 3) 레시피 파싱
    recipe_data = parse_structured_recipe(full_recipe_text)
    dish_name_to_speak = recipe_data["dish_name"] if recipe_data["dish_name"] != "정보 없음" else dish_query
    ingredients = recipe_data.get("ingredients", [])
    tools = recipe_data.get("tools", [])
    steps = recipe_data.get("steps", [])
    tips = recipe_data.get("tips", "특별한 팁 없음")

    if not steps:
        tts_speak(f"죄송합니다. '{dish_name_to_speak}' 레시피의 단계 정보를 분석하지 못했어요.")
        return

    # 4) 재료 및 도구 안내
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

    # 5) “시작/다음” 대기
    tts_speak("모든 재료와 도구가 준비되셨으면, '시작' 또는 '다음'이라고 말씀해주세요.")
    ready_to_start = False
    while not ready_to_start:
        cmd = listen_for_trigger(timeout_sec=20)
        if any(k in cmd for k in ["시작", "준비 됐어", "준비됐어", "다음", "네", "응", "next", "start", "yes", "ok"]):
            ready_to_start = True
        else:
            tts_speak("계속하려면 '시작' 또는 '다음'이라고 말씀해주세요.")

    # 6) 첫 단계 안내
    current_step_idx = 0
    tts_speak(f"좋아요! 첫 번째 단계입니다. {steps[current_step_idx]}")

    # 7) 단계별 음성 안내 루프
    while current_step_idx < len(steps):
        tts_speak("다음 행동을 말씀해주세요: '다음 단계', '이전 단계', '다시 알려줘', '재료 확인', '도구 확인', 또는 '요리 종료'.")
        cmd = listen_for_trigger(timeout_sec=25)

        if not cmd:
            tts_speak("명령을 듣지 못했어요. 어떻게 할까요?")
            continue

        # 7-1) 다음 단계
        if any(k in cmd for k in ["다음 단계", "다음", "넥스트", "next step", "next"]):
            current_step_idx += 1
            if current_step_idx < len(steps):
                tts_speak(f"{current_step_idx + 1} 단계입니다. {steps[current_step_idx]}")
            else:
                tts_speak("축하합니다! 모든 단계가 완료되었습니다. 맛있게 드세요!")
                if tips and tips != "특별한 팁 없음":
                    tts_speak(f"마지막으로, 유용한 팁입니다: {tips}")
                break

        # 7-2) 현재 단계 반복
        elif any(k in cmd for k in ["다시 알려줘", "반복", "리핏", "repeat", "again", "뭐라고"]):
            tts_speak(f"네, 다시 알려드릴게요. 현재 {current_step_idx + 1} 단계는 {steps[current_step_idx]} 입니다.")

        # 7-3) 이전 단계
        elif any(k in cmd for k in ["이전 단계", "이전", "프리비어스", "previous step", "previous"]):
            if current_step_idx > 0:
                current_step_idx -= 1
                tts_speak(f"{current_step_idx + 1} 단계로 돌아갑니다. {steps[current_step_idx]}")
            else:
                tts_speak("이미 첫 번째 단계입니다. 이전 단계로 돌아갈 수 없어요.")

        # 7-4) 재료 확인
        elif any(k in cmd for k in ["재료 확인", "재료 목록", "재료 뭐였지", "ingredients"]):
            if ingredients:
                ing_list_str = ", ".join(ingredients)
                tts_speak(f"이 요리에 사용된 전체 재료는 {ing_list_str} 입니다.")
            else:
                tts_speak("죄송하지만, 재료 정보를 불러올 수 없네요.")

        # 7-5) 도구 확인
        elif any(k in cmd for k in ["도구 확인", "도구 목록", "도구 뭐였지", "tools"]):
            if tools:
                tool_list_str = ", ".join(tools)
                tts_speak(f"이 요리에 사용된 전체 도구는 {tool_list_str} 입니다.")
            else:
                tts_speak("죄송하지만, 도구 정보를 불러올 수 없네요.")

        # 7-6) 현재 단계 확인
        elif any(k in cmd for k in ["현재 단계", "지금 몇 단계", "what step"]):
            tts_speak(f"지금은 {current_step_idx + 1} 단계이고, 내용은 다음과 같습니다. {steps[current_step_idx]}")

        # 7-7) 요리 종료
        elif any(k in cmd for k in ["요리 종료", "그만할래", "종료", "스탑", "stop", "exit"]):
            tts_speak("알겠습니다. 요리 안내를 종료합니다. 이용해주셔서 감사합니다!")
            break

        # 7-8) 기타(알 수 없는 명령)
        else:
            tts_speak(f"죄송해요. '{cmd}'라고 들렸어요. 다시 한번 말씀해 주시겠어요?")


if __name__ == "__main__":
    # 환경 변수 확인
    gemini_key = os.getenv("GEMINI_API_KEY")
    gcp_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not gemini_key:
        print("오류: 환경 변수 'GEMINI_API_KEY'가 설정되지 않았습니다.")
    if not gcp_creds:
        print("오류: 환경 변수 'GOOGLE_APPLICATION_CREDENTIALS'가 설정되지 않았습니다.")

    if gemini_key and gcp_creds:
        # PyAudio 및 마이크 확인
        try:
            import pyaudio  # type: ignore
            p = pyaudio.PyAudio()
            p.terminate()
            print("PyAudio 확인 완료.")
            run_step_by_step()
        except ImportError:
            print("오류: PyAudio 라이브러리를 찾을 수 없습니다. 설치가 필요합니다.")
        except Exception as e_main:
            if "PortAudio" in str(e_main) or "No Default Input Device Available" in str(e_main):
                print(f"오디오 장치 오류 또는 PortAudio 문제: {e_main}")
                print("마이크가 연결되어 있는지, PortAudio가 설치되었는지 확인해주세요.")
                print("Linux: sudo apt-get install portaudio19-dev python3-pyaudio")
                print("macOS: brew install portaudio && pip install pyaudio")
            else:
                print(f"실행 중 예기치 않은 오류 발생: {e_main}")
    else:
        print("필수 환경 변수가 설정되지 않아 프로그램을 실행할 수 없습니다.")
