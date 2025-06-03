from flask import Flask, request, jsonify, render_template
import os
import sys
import re

from generate_recipe_gemini_api import generate_recipe  # Gemini 호출 모듈 그대로 사용

app = Flask(__name__)

@app.route("/")
def index():
    # 마이크 입력 화면
    return render_template("index.html")

@app.route("/recipe")
def recipe_page():
    # URL 파라미터에서 dish 가져와서 recipe.html 렌더링
    dish = request.args.get("dish", "")
    if not dish:
        # dish가 없으면 index로 리다이렉트
        return render_template("index.html")
    return render_template("recipe.html", dish=dish)

@app.route("/api/recipe")
def api_recipe():
    """
    클라이언트에서 `?dish=...` 파라미터로 요청하면,
    generate_recipe()를 호출하여 JSON으로 결과를 반환합니다.
    """
    dish = request.args.get("dish", "").strip()
    if not dish:
        return jsonify({"error": "No dish parameter provided."}), 400

    # 1) Gemini API로 레시피 원문 획득
    full_text = generate_recipe(dish)
    if full_text.startswith("Error"):
        return jsonify({"error": full_text}), 500

    # 2) parse_structured_recipe를 내부적으로 쓰거나, 간단히 파싱
    #    여기서는 미리 구현된 parse_structured_recipe 로직을 재사용합니다.
    #    parse_structured_recipe 함수는 recipe_voice_assistant.py에 정의되어 있지만,
    #    여기서는 다시 간단히 복붙해 두겠습니다.

    def parse_structured_recipe(recipe_text: str) -> dict:
        parsed_data = {
            "dish_name": dish,
            "total_time": "",
            "ingredients": [],
            "tools": [],
            "steps": [],
            "tips": ""
        }
        try:
            # **Tools** 블록
            tools_match = re.search(
                r"\*\*필요한 도구:\*\*\s*\n(.*?)(?=\n\*\*만드는 단계:\*\*|\Z)", 
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if tools_match:
                tools_block = tools_match.group(1).strip()
                parsed_data["tools"] = [
                    line.strip().lstrip("- ").strip()
                    for line in tools_block.split("\n") if line.strip().startswith("-")
                ]

            # **Ingredients** 블록
            ingredients_match = re.search(
                r"\*\*재료:\*\*\s*\n(.*?)(?=\n\*\*필요한 도구:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if ingredients_match:
                ing_block = ingredients_match.group(1).strip()
                parsed_data["ingredients"] = [
                    line.strip().lstrip("- ").strip()
                    for line in ing_block.split("\n") if line.strip().startswith("-")
                ]

            # **Steps** 블록
            steps_match = re.search(
                r"\*\*만드는 단계:\*\*\s*\n(.*?)(?=\n\*\*팁:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if steps_match:
                steps_block = steps_match.group(1).strip()
                raw_steps = [
                    line.strip() for line in steps_block.split("\n")
                    if re.match(r"^\d+\.\s+", line.strip())
                ]
                parsed_data["steps"] = [
                    re.sub(r"^\d+\.\s*", "", step).strip() for step in raw_steps
                ]

            # **Tips** 블록 (선택사항)
            tips_match = re.search(r"\*\*팁:\*\*\s*\n(.*?)(?=\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
            if tips_match:
                parsed_data["tips"] = tips_match.group(1).strip()

        except Exception as e:
            # 파싱 오류 시 빈 리스트로 내려줍니다.
            parsed_data["ingredients"] = parsed_data.get("ingredients", [])
            parsed_data["tools"] = parsed_data.get("tools", [])
            parsed_data["steps"] = parsed_data.get("steps", [])
            parsed_data["tips"] = parsed_data.get("tips", "")

        return parsed_data

    parsed = parse_structured_recipe(full_text)
    parsed["dish_name"] = dish  # 엔드포인트 호출한 dish 그대로 반환

    return jsonify(parsed)


if __name__ == "__main__":
    # 실행 전에 반드시 환경 변수 확인:
    #   $Env:GEMINI_API_KEY  와  $Env:GOOGLE_APPLICATION_CREDENTIALS (서비스 계정 JSON 경로)
    gemini_key = os.getenv("GEMINI_API_KEY")
    gcp_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not gemini_key:
        print("Error: GEMINI_API_KEY is not set.")
        sys.exit(1)
    if not gcp_creds:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS is not set.")
        sys.exit(1)
    app.run(host="0.0.0.0", port=5000, debug=True)
