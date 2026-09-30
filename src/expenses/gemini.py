import json
import os
import random
import time

import dotenv
from google import genai
from google.genai import types

dotenv.load_dotenv()


def gemini_category(prompt: str, data: dict | list | str) -> types.GenerateContentResponse:
    """Invokes Google Gemini AI with automatic exponential backoff retry on 503/429 and resilient model fallbacks."""
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Priority list of models to try
    models_to_try = [
        primary_model,
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
    ]
    models_sequence = list(dict.fromkeys(models_to_try))

    if isinstance(data, str):
        data_str = data
    else:
        data_str = json.dumps(data, ensure_ascii=False)

    content = f"{prompt}\n\nCategorize os seguintes dados brutos:\n{data_str}"

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
    )

    last_error = None
    for model_name in models_sequence:
        for attempt in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=content, config=generate_content_config
                )
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                err_str = str(exc).lower()
                # If temporary spike (503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, high demand), wait and retry
                if (
                    "503" in err_str
                    or "unavailable" in err_str
                    or "429" in err_str
                    or "demand" in err_str
                ):
                    wait_time = (2**attempt) + random.uniform(0.5, 1.5)
                    time.sleep(wait_time)
                    continue
                # If model is 404 NOT_FOUND or deprecated, break immediately to try next model
                if "404" in err_str or "not found" in err_str or "no longer available" in err_str:
                    break
                # Other transient errors: brief pause
                time.sleep(1)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to generate content with Gemini AI across all fallback models.")
