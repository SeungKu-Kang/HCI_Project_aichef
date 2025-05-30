# llm_stt_tts_gemini.py
# STT -> Gemini Developer API 호출 -> TTS 통합 예제
"""
사전 준비:
1. Python 3.8+ 설치, venv 사용 권장
2. Google Cloud Speech-to-Text, Text-to-Speech API 활성화 및 서비스 계정 키 설정
   (GOOGLE_APPLICATION_CREDENTIALS 환경 변수에 서비스 계정 JSON 파일 경로 설정)
3. Gemini Developer API 키 발급 및 GEMINI_API_KEY 환경 변수 설정
4. OS별 PortAudio(pyaudio) 설치 (예: Ubuntu: sudo apt-get install portaudio19-dev python3-pyaudio)
5. pip install --upgrade google-cloud-speech google-cloud-texttospeech google-generativeai pyaudio wave
6. python llm_stt_tts_gemini.py 로 실행
"""
import os
import queue
import pyaudio
from google.cloud import speech, texttospeech
# 변경: google.genai 대신 google.generativeai 임포트
from google import generativeai as genai

# Gemini Developer API 클라이언트 설정
# 환경 변수로 GEMINI_API_KEY 설정 필요
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# STT/TTS 설정 상수
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
FORMAT = pyaudio.paInt16
CHANNELS = 1

audio_queue = queue.Queue()

# 마이크 스트림 클래스
class MicrophoneStream:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self._callback
        )

    def _callback(self, in_data, frame_count, time_info, status):
        audio_queue.put(in_data)
        return None, pyaudio.paContinue

    def start(self):
        self.stream.start_stream()
        print("[Mic] 실시간 대기 중... 말씀해주세요 (Ctrl+C로 종료)")

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        audio_queue.put(None)
        print("[Mic] 녹음 종료")

# STT 요청 생성기
def request_generator():
    while True:
        chunk = audio_queue.get()
        if chunk is None:
            return
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

# Gemini 호출 함수
def generate_recipe(prompt_text: str) -> str:
    # 다중턴 대화를 위해 chat 세션 생성
    # models/gemini-pro-latest 또는 models/gemini-1.5-flash-latest 중 선택하여 사용
    # 여기서는 'models/gemini-1.5-pro-latest'를 사용합니다.
    model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")
    chat = model.start_chat(history=[]) # chat 세션 시작
    response = chat.send_message(prompt_text)
    return response.text.strip()

# TTS 호출 함수
def tts_speak(text: str):
    tts_client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    resp = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    output_file = "recipe_reply.wav"
    with open(output_file, 'wb') as f:
        f.write(resp.audio_content)
    
    # OS에 따라 오디오 재생 명령어 선택
    if os.name == 'posix': # Linux, macOS
        if os.uname().sysname == 'Darwin': # macOS
            os.system(f"afplay {output_file}")
        else: # Linux
            os.system(f"aplay {output_file}")
    elif os.name == 'nt': # Windows
        print(f"Windows에서는 '{output_file}' 파일을 직접 실행하여 들어주세요.")
        try:
            os.startfile(output_file)
        except AttributeError:
            print("Windows에서 오디오 파일을 재생하려면 추가적인 라이브러리(예: simpleaudio)가 필요합니다.")

# 메인 함수
if __name__ == '__main__':
    mic = MicrophoneStream()
    stt_client = speech.SpeechClient()
    stt_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="ko-KR"
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=stt_config,
        interim_results=False
    )
    try:
        mic.start()
        for resp in stt_client.streaming_recognize(
            config=streaming_config,
            requests=request_generator()
        ):
            for result in resp.results:
                if result.is_final:
                    user_query = result.alternatives[0].transcript
                    print(f"[STT] {user_query}")
                    recipe = generate_recipe(
                        f"요리 레시피와 단계별 필요한 도구를 알려주세요: {user_query}"
                    )
                    print(f"[Gemini] {recipe}")
                    tts_speak(recipe)
                    # 첫 번째 최종 결과 후 루프 종료
                    break
    except KeyboardInterrupt:
        print("Ctrl+C 감지됨, 프로그램 종료 중...")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        mic.stop()
        print("프로그램 종료")