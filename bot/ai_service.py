import json
import re
import logging
from openai import OpenAI

from .config import OPENAI_API_KEY, SYSTEM_PROMPT
from .estimate_generator import get_positions_prompt

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


def extract_json(text: str) -> dict | None:
    """Извлекает JSON из ответа модели, удаляя комментарии и исправляя типичные ошибки"""
    
    # Ищем JSON-блок в markdown ```json ... ``` или просто { ... }
    # Сначала пробуем найти в code block
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if code_block_match:
        json_str = code_block_match.group(1)
    else:
        # Ищем просто JSON объект
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group()
        else:
            logger.warning("No JSON found in response")
            return None
    
    # Очищаем JSON от типичных проблем
    # 1. Удаляем однострочные комментарии // ...
    json_str = re.sub(r'//[^\n]*', '', json_str)
    # 2. Удаляем многострочные комментарии /* ... */
    json_str = re.sub(r'/\*[\s\S]*?\*/', '', json_str)
    # 3. Удаляем запятые перед закрывающими скобками (trailing commas)
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    # 4. Заменяем одинарные кавычки на двойные (иногда GPT так делает)
    # Это опасно, поэтому делаем аккуратно — только для ключей
    
    try:
        parsed = json.loads(json_str)
        logger.info(f"Successfully parsed JSON with keys: {list(parsed.keys())}")
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.error(f"JSON string (first 1000 chars): {json_str[:1000]}")
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
