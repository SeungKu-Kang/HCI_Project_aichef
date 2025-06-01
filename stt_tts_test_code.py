# stt_tts_test_code.py

import os
import queue
import threading
import pyaudio
import wave
from google.cloud import speech, texttospeech

# 오디오 스트림 설정
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
FORMAT = pyaudio.paInt16
CHANNELS = 1

audio_queue = queue.Queue()

# 마이크에서 들어오는 오디오를 큐에 저장
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
        return (None, pyaudio.paContinue)

    def start(self):
        self.stream.start_stream()
        print("[Mic] 실시간 대기 중... Ctrl+C로 종료")

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        audio_queue.put(None)
        print("[Mic] 녹음 종료")

# Streaming 요청 생성기
def request_generator():
    while True:
        chunk = audio_queue.get()
        if chunk is None:
            return
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

# (이 파일만으로는 콘솔 STT+TTS 전체 흐름이 동작함)
# 필요한 경우 하단의 예제 함수를 참조하세요.

def streaming_transcribe_and_synthesize():
    stt_client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="ko-KR",
        model="default"
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=False
    )
    responses = stt_client.streaming_recognize(
        config=streaming_config,
        requests=request_generator()
    )

    tts_client = texttospeech.TextToSpeechClient()
    for resp in responses:
        for result in resp.results:
            if result.is_final:
                text = result.alternatives[0].transcript
                print(f"[STT] {text}")
                # TTS 합성
                synthesis_input = texttospeech.SynthesisInput(text=text)
                voice = texttospeech.VoiceSelectionParams(
                    language_code="ko-KR",
                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16
                )
                tts_resp = tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                # WAV 파일로 저장 및 재생
                output = "tts_output.wav"
                with open(output, 'wb') as f:
                    f.write(tts_resp.audio_content)
                os.system(f"aplay {output}")  # macOS: afplay
                os.remove(output)

if __name__ == '__main__':
    mic = MicrophoneStream()
    try:
        mic.start()
        streaming_transcribe_and_synthesize()
    except KeyboardInterrupt:
        pass
    finally:
        mic.stop()
    print("프로그램 종료")
