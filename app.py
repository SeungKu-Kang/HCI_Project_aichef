from flask import Flask, request, jsonify, render_template
import os, sys, re
from generate_recipe_gemini_api import generate_recipe

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/recipe")
def recipe_page():
    dish = request.args.get("dish", "")
    if not dish:
        return render_template("index.html")
    return render_template("recipe.html", dish=dish)

@app.route("/api/recipe")
def api_recipe():
    dish = request.args.get("dish", "").strip()
    if not dish:
        return jsonify({"error": "No dish parameter provided."}), 400

    full_text = generate_recipe(dish)
    if full_text.startswith("Error"):
        return jsonify({"error": full_text}), 500

    def parse_structured_recipe(recipe_text: str) -> dict:
        parsed_data = {"dish_name": dish, "tools": [], "ingredients": [], "steps": [], "tips": ""}
        try:
            # Tools
            tools_match = re.search(
                r"\*\*필요한 도구:\*\*\s*\n(.*?)(?=\n\*\*만드는 단계:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if tools_match:
                block = tools_match.group(1).strip()
                parsed_data["tools"] = [
                    line.strip().lstrip("- ").strip()
                    for line in block.split("\n") if line.strip().startswith("-")
                ]

            # Ingredients
            ingredients_match = re.search(
                r"\*\*재료:\*\*\s*\n(.*?)(?=\n\*\*필요한 도구:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if ingredients_match:
                block = ingredients_match.group(1).strip()
                parsed_data["ingredients"] = [
                    line.strip().lstrip("- ").strip()
                    for line in block.split("\n") if line.strip().startswith("-")
                ]

            # Steps
            steps_match = re.search(
                r"\*\*만드는 단계:\*\*\s*\n(.*?)(?=\n\*\*팁:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if steps_match:
                block = steps_match.group(1).strip()
                raw = [
                    line.strip() for line in block.split("\n")
                    if re.match(r"^\d+\.\s+", line.strip())
                ]
                parsed_data["steps"] = [
                    re.sub(r"^\d+\.\s*", "", s).strip() for s in raw
                ]

            # Tips
            tips_match = re.search(r"\*\*팁:\*\*\s*\n(.*?)(?=\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
            if tips_match:
                parsed_data["tips"] = tips_match.group(1).strip()

        except:
            pass

        return parsed_data

    parsed = parse_structured_recipe(full_text)
    parsed["dish_name"] = dish
    return jsonify(parsed)

@app.route("/api/image")
def api_image():
    dish = request.args.get("dish", "").strip()
    step_index = request.args.get("step_index", "").strip()
    if not dish or step_index == "":
        return jsonify({"error": "Missing parameters."}), 400

    from generate_recipe_gemini_api import generate_recipe

    full_text = generate_recipe(dish)
    if full_text.startswith("Error"):
        return jsonify({"error": full_text}), 500

    def parse_structured_recipe(recipe_text: str) -> dict:
        parsed_data = {"steps": []}
        try:
            steps_match = re.search(
                r"\*\*만드는 단계:\*\*\s*\n(.*?)(?=\n\*\*팁:\*\*|\Z)",
                recipe_text, re.DOTALL | re.IGNORECASE
            )
            if steps_match:
                block = steps_match.group(1).strip()
                raw = [
                    line.strip() for line in block.split("\n")
                    if re.match(r"^\d+\.\s+", line.strip())
                ]
                parsed_data["steps"] = [
                    re.sub(r"^\d+\.\s*", "", s).strip() for s in raw
                ]
        except:
            pass
        return parsed_data

    parsed = parse_structured_recipe(full_text)
    steps = parsed.get("steps", [])
    try:
        idx = int(step_index)
        current_step_desc = steps[idx]
    except:
        return jsonify({"error": "Invalid step index."}), 400

    # 실제 AI 이미지 생성 모델 호출
    try:
        import generativeai as genai
        model = genai.GenerativeModel(model_name="models/image-alpha-001")
        prompt = f"An illustrative photo of how to do step {idx+1} of making {dish}: {current_step_desc}"
        response = model.generate_image(prompt=prompt, size="512x512")
        image_url = response.data[0].url
    except Exception as e:
        print(f"[Image API Error] {e}")
        image_url = f"https://via.placeholder.com/300x200?text={dish.replace(' ', '+')}_step{idx+1}"

    return jsonify({"url": image_url})

if __name__ == "__main__":
    gemini_key = os.getenv("GEMINI_API_KEY")
    gcp_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not gemini_key or not gcp_creds:
        print("Error: Required environment variables not set.")
        sys.exit(1)
    app.run(host="0.0.0.0", port=5000, debug=True)
