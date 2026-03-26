# 🚀 Сметомёт AI

Telegram-бот для автоматического составления смет видеопродакшна на основе описания проекта в свободной форме.

## Возможности

- 💬 Описывай проект в свободной форме — бот сам разберётся
- 🤖 AI анализирует описание и подбирает нужные позиции из справочника
- ❓ Задаёт уточняющие вопросы, если информации недостаточно
- 📊 Генерирует красивую смету в Excel
- 💰 Автоматически считает наценку, итоги и прибыль

## Установка

### 1. Клонируй репозиторий и установи зависимости

```bash
cd СметомётAI
pip install -r requirements.txt
```

### 2. Создай Telegram бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Придумай имя и username для бота
4. Скопируй токен

### 3. Получи OpenAI API ключ

1. Зарегистрируйся на [platform.openai.com](https://platform.openai.com)
2. Перейди в [API Keys](https://platform.openai.com/api-keys)
3. Создай новый ключ

### 4. Настрой переменные окружения

```bash
cp .env.example .env
```

Отредактируй `.env`:

```
TELEGRAM_BOT_TOKEN=твой_токен_от_botfather
OPENAI_API_KEY=sk-твой_ключ_openai
```

### 5. Запусти бота

```bash
python run.py
```

## Использование

1. Открой своего бота в Telegram
2. Отправь `/start`
3. Опиши проект, например:

   > Нужно снять рекламный ролик для кофейни. 2 съёмочных дня, 3 актёра, хронометраж 2 минуты. Нужны титры и цветокоррекция.

4. Бот задаст уточняющие вопросы или сразу выдаст смету
5. Напиши `/excel` чтобы скачать смету в Excel

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать заново |
| `/clear` | Сбросить текущий диалог |
| `/estimate` | Получить смету по имеющейся информации |
| `/excel` | Скачать смету в Excel |

## Структура проекта

```
СметомётAI/
├── bot/
│   ├── __init__.py
│   ├── config.py          # Настройки и промпты
│   ├── main.py             # Telegram бот
│   ├── ai_service.py       # Интеграция с OpenAI
│   ├── estimate_generator.py # Генерация Excel
│   └── positions.json      # Справочник услуг
├── run.py                  # Точка входа
├── requirements.txt
├── .env.example
└── README.md
```

## Настройка справочника услуг

Справочник услуг хранится в `bot/positions.json`. Он автоматически сгенерирован из Excel-файла `Сметомёт 2.0.xlsx`.

Чтобы обновить справочник после изменения Excel:

```bash
python -c "
import openpyxl
import json

wb = openpyxl.load_workbook('Сметомёт 2.0.xlsx')
sheet = wb['Позиции']

services = {}
current_category = None

for row_idx in range(2, sheet.max_row + 1):
    position = sheet.cell(row_idx, 2).value
    cost = sheet.cell(row_idx, 3).value
    level = sheet.cell(row_idx, 5).value
    
    if not position or 'Проект:' in str(position):
        continue
    if cost is None:
        current_category = position
    else:
        key = f'{current_category}|{position}'
        if key not in services:
            services[key] = {'category': current_category, 'name': position, 'levels': {}}
        lvl = int(level) if isinstance(level, (int, float)) else 3
        services[key]['levels'][lvl] = {'cost': int(cost), 'default': False}

data = {'categories': ['Препродакшн', 'Продакшн', 'Постпродакшн'], 'services': list(services.values())}
with open('bot/positions.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'Обновлено: {len(services)} услуг')
"
```

## Лицензия

MIT
