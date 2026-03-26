import json
import re
from openai import OpenAI

from .config import OPENAI_API_KEY, SYSTEM_PROMPT
from .estimate_generator import get_positions_prompt


client = OpenAI(api_key=OPENAI_API_KEY)


def extract_json(text: str) -> dict | None:
    """Извлекает JSON из ответа модели"""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return None
    return None


def analyze_project(conversation_history: list[dict]) -> dict:
    """
    Анализирует описание проекта и возвращает структуру для сметы
    или уточняющие вопросы.
    
    Args:
        conversation_history: История сообщений [{role: "user"/"assistant", content: "..."}]
    
    Returns:
        {
            "ready": True/False,
            "estimate": {...} или "questions": [...]
            "text_response": "..." - ответ для отображения пользователю
        }
    """
    
    positions_context = get_positions_prompt()
    full_system_prompt = f"{SYSTEM_PROMPT}\n\n{positions_context}"
    
    messages = [{"role": "system", "content": full_system_prompt}]
    messages.extend(conversation_history)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.3,
        max_tokens=4000
    )
    
    assistant_message = response.choices[0].message.content
    
    parsed = extract_json(assistant_message)
    
    if parsed and parsed.get("ready"):
        return {
            "ready": True,
            "estimate": parsed,
            "text_response": assistant_message
        }
    elif parsed and parsed.get("questions"):
        questions_text = "Уточни, пожалуйста:\n" + "\n".join(
            f"• {q}" for q in parsed["questions"]
        )
        return {
            "ready": False,
            "questions": parsed["questions"],
            "text_response": questions_text
        }
    else:
        return {
            "ready": False,
            "text_response": assistant_message
        }
