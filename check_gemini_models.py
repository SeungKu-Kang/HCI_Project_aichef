import os
from google import generativeai as genai

# Gemini API 키 설정 (환경 변수에서 가져오기)
# 'YOUR_API_KEY' 대신 실제 API 키를 직접 입력해도 되지만, 환경 변수 사용을 권장합니다.
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("사용 가능한 Gemini 모델 목록:")
print("-----------------------------------")
for m in genai.list_models():
    # generateContent 메서드를 지원하는 모델만 필터링합니다.
    if "generateContent" in m.supported_generation_methods:
        print(f"모델 이름: {m.name}")
        print(f"  지원 메서드: {m.supported_generation_methods}")
        print(f"  설명: {m.description}")
        print("---")