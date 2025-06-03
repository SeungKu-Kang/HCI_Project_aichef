# recipe_voice_assistant.py

import os
import re
import sys
from google.oauth2 import service_account
from google.cloud import speech
from generate_recipe_gemini_api import generate_recipe, tts_speak
from stt_tts_test_code import MicrophoneStream, request_generator

# ─── Load GCP Credentials ───
def load_credentials():
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS is not set.")
        print("Please set this environment variable to the path of your service account JSON.")
        sys.exit(1)
    if not os.path.isfile(cred_path):
        print(f"Error: Credential file not found at {cred_path}")
        print("Ensure the path is correct.")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(cred_path)

CREDS = load_credentials()

# ─── STT Listening Function ───
def listen_for_trigger(timeout_sec: int = 15) -> str:
    """
    Capture microphone input and return it as a lowercase English string.
    """
    client = speech.SpeechClient(credentials=CREDS)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=False
    )

    mic = MicrophoneStream()
    mic.start()
    transcript = ""

    print("[STT] Listening for command...")

    try:
        for resp in client.streaming_recognize(
            streaming_config, request_generator()
        ):
            if resp.results and resp.results[0].is_final:
                transcript = resp.results[0].alternatives[0].transcript.lower().strip()
                print(f"[STT] Recognized: '{transcript}'")
                break
    except Exception as e:
        print(f"[STT Error] {e}")
    finally:
        mic.stop()

    return transcript

# ─── Extract Dish Name: fixed “tell me how to make [dish]” ───
def extract_dish_name(query: str) -> str:
    """
    Only accept the format:
      "tell me how to make [dish name]"

    Returns the [dish name] portion, or an empty string if pattern does not match.
    """
    if not query:
        return ""

    # Expecting exactly “tell me how to make ” at the start
    pattern = r"^tell me how to make\s+(.+)$"
    match = re.match(pattern, query, re.IGNORECASE)
    if match:
        dish = match.group(1).strip()
        return dish

    return ""  # pattern not matched

# ─── Parse Structured Recipe (English headings) ───
def parse_structured_recipe(recipe_text: str) -> dict:
    data = {
        "dish_name": "Unknown",
        "total_time": "Unknown",
        "ingredients": [],
        "tools": [],
        "steps": [],
        "tips": "No special tips"
    }

    if not recipe_text or recipe_text.startswith("Error"):
        print(f"[Parser] Invalid recipe text: {recipe_text}")
        return data

    try:
        # Dish Name
        dn = re.search(r"【Dish Name】:\s*(.+?)(?=\n|$)", recipe_text, re.IGNORECASE)
        if dn:
            data["dish_name"] = dn.group(1).strip()

        # Total Time
        tt = re.search(r"【Total Time】:\s*(.+?)(?=\n|$)", recipe_text, re.IGNORECASE)
        if tt:
            data["total_time"] = tt.group(1).strip()

        # Ingredients block
        ing_block = re.search(
            r"【Ingredients】:\s*\n(.*?)(?=\n【Tools】:|\n【Steps】:|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if ing_block:
            lines = ing_block.group(1).strip().split("\n")
            data["ingredients"] = [
                line.strip().lstrip("- ").strip()
                for line in lines if line.strip().startswith("-")
            ]

        # Tools block
        tools_block = re.search(
            r"【Tools】:\s*\n(.*?)(?=\n【Steps】:|\n【Tips】:|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if tools_block:
            lines = tools_block.group(1).strip().split("\n")
            data["tools"] = [
                line.strip().lstrip("- ").strip()
                for line in lines if line.strip().startswith("-")
            ]

        # Steps block
        steps_block = re.search(
            r"【Steps】:\s*\n(.*?)(?=\n【Tips】:|\Z)",
            recipe_text, re.DOTALL | re.IGNORECASE
        )
        if steps_block:
            lines = steps_block.group(1).strip().split("\n")
            raw_steps = [
                line.strip() for line in lines
                if re.match(r"^\d+\.\s+", line.strip())
            ]
            data["steps"] = [
                re.sub(r"^\d+\.\s*", "", step).strip() for step in raw_steps
            ]

        # Tips block
        tips_block = re.search(r"【Tips】:\s*(.+?)(?=\Z)", recipe_text, re.DOTALL | re.IGNORECASE)
        if tips_block:
            data["tips"] = tips_block.group(1).strip()

    except Exception as e:
        print(f"[Parser Error] Parsing recipe failed: {e}")
        print(f"Partial text: {recipe_text[:300]}")

    return data

# ─── Main: Step-by-Step Voice Loop ───
def run_step_by_step():
    # 1) Prompt in English
    prompt_en = "Hello! To begin, please say: 'Tell me how to make [dish name]'."
    print(prompt_en)
    tts_speak(prompt_en)

    # 2) Listen for exact phrase
    raw_query = listen_for_trigger()
    dish_query = extract_dish_name(raw_query)
    print(f"[Dish Query] Raw: '{raw_query}' → Extracted: '{dish_query}'")

    # 3) If pattern not matched, ask again
    if not dish_query:
        tts_speak("Please say exactly: 'Tell me how to make [dish name]'.")
        return

    # 4) Confirm and look up recipe
    tts_speak(f"Looking up the recipe for {dish_query}. Please wait.")

    # 5) Fetch recipe
    full_recipe_text = generate_recipe(dish_query)
    if not full_recipe_text or full_recipe_text.startswith("Error"):
        tts_speak(f"Sorry, I couldn't retrieve the recipe for {dish_query}. {full_recipe_text}")
        return

    # 6) Parse recipe
    recipe_data = parse_structured_recipe(full_recipe_text)
    dish_to_speak = recipe_data["dish_name"] if recipe_data["dish_name"] != "Unknown" else dish_query
    ingredients = recipe_data.get("ingredients", [])
    tools = recipe_data.get("tools", [])
    steps = recipe_data.get("steps", [])
    tips = recipe_data.get("tips", "No special tips")

    if not steps:
        tts_speak(f"Sorry, I couldn't parse the steps for {dish_to_speak}.")
        return

    # 7) Announce ingredients and tools
    tts_speak(f"Starting instructions for {dish_to_speak}.")
    if ingredients:
        ing_str = ", ".join(ingredients)
        tts_speak(f"You will need the following ingredients: {ing_str}.")
    else:
        tts_speak("Ingredient list is not available.")

    if tools:
        tools_str = ", ".join(tools)
        tts_speak(f"You will also need these tools: {tools_str}.")
    else:
        tts_speak("Tool list is not available.")

    # 8) Wait for “start” or “next”
    tts_speak("When you are ready, say 'Start' or 'Next'.")
    ready = False
    while not ready:
        cmd = listen_for_trigger(timeout_sec=20)
        if any(k in cmd for k in ["start", "next", "yes", "ok"]):
            ready = True
        else:
            tts_speak("Please say 'Start' or 'Next' when ready.")

    # 9) Read first step
    current_idx = 0
    tts_speak(f"Step 1: {steps[current_idx]}")

    # 10) Step navigation loop
    while current_idx < len(steps):
        tts_speak("Say 'Next step', 'Previous step', 'Repeat', 'Ingredients', 'Tools', or 'Finish'.")
        cmd = listen_for_trigger(timeout_sec=25)

        if not cmd:
            tts_speak("Sorry, I didn't catch that. What would you like to do?")
            continue

        # Next step
        if any(k in cmd for k in ["next step", "next"]):
            current_idx += 1
            if current_idx < len(steps):
                tts_speak(f"Step {current_idx + 1}: {steps[current_idx]}")
            else:
                tts_speak("You have completed all steps. Enjoy your meal!")
                if tips and tips.lower() != "no special tips":
                    tts_speak(f"One final tip: {tips}")
                break

        # Repeat current step
        elif any(k in cmd for k in ["repeat", "again"]):
            tts_speak(f"Repeating step {current_idx + 1}: {steps[current_idx]}")

        # Previous step
        elif any(k in cmd for k in ["previous step", "previous"]):
            if current_idx > 0:
                current_idx -= 1
                tts_speak(f"Going back to step {current_idx + 1}: {steps[current_idx]}")
            else:
                tts_speak("You are already at the first step.")

        # Ingredients inquiry
        elif any(k in cmd for k in ["ingredients", "what ingredients", "list ingredients"]):
            if ingredients:
                ing_str = ", ".join(ingredients)
                tts_speak(f"Ingredients: {ing_str}.")
            else:
                tts_speak("Ingredient list is not available.")

        # Tools inquiry
        elif any(k in cmd for k in ["tools", "what tools", "list tools"]):
            if tools:
                tools_str = ", ".join(tools)
                tts_speak(f"Tools: {tools_str}.")
            else:
                tts_speak("Tool list is not available.")

        # Current step inquiry
        elif any(k in cmd for k in ["current step", "what step", "which step"]):
            tts_speak(f"You are on step {current_idx + 1}: {steps[current_idx]}")

        # Finish
        elif any(k in cmd for k in ["finish", "stop", "exit"]):
            tts_speak("Okay, ending the recipe guidance. Thank you!")
            break

        # Unrecognized command
        else:
            tts_speak(f"Sorry, I didn't understand '{cmd}'. Please try again.")

if __name__ == "__main__":
    key = os.getenv("GEMINI_API_KEY")
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not key:
        print("Error: GEMINI_API_KEY is not set.")
    if not creds:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS is not set.")

    if key and creds:
        try:
            import pyaudio  # type: ignore
            p = pyaudio.PyAudio()
            p.terminate()
            print("PyAudio check passed.")
            run_step_by_step()
        except ImportError:
            print("Error: PyAudio library not found. Please install it.")
        except Exception as e_main:
            if "PortAudio" in str(e_main) or "No Default Input Device Available" in str(e_main):
                print(f"Audio device or PortAudio issue: {e_main}")
                print("Make sure your microphone is connected and PortAudio is installed.")
                print("Linux: sudo apt-get install portaudio19-dev python3-pyaudio")
                print("macOS: brew install portaudio && pip install pyaudio")
            else:
                print(f"Unexpected error: {e_main}")
    else:
        print("Required environment variables are missing. Cannot run.")
