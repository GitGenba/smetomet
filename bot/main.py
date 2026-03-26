import logging
import os
import json
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

from .config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY
from .ai_service import analyze_project
from .estimate_generator import generate_estimate_excel, format_estimate_text

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# OpenAI клиент для Whisper
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Хранилище смет по ID (для возможности вернуться к любой смете)
estimates_storage = {}


def generate_estimate_id():
    """Генерирует уникальный ID для сметы"""
    import time
    return f"est_{int(time.time() * 1000)}"


async def transcribe_voice(file_path: str) -> str:
    """Транскрибирует голосовое сообщение через OpenAI Whisper"""
    with open(file_path, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru"
        )
    return transcript.text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    context.user_data['conversation'] = []
    context.user_data['current_estimate_id'] = None
    context.user_data['edit_mode'] = False
    
    welcome_message = """👋 Привет! Я — Сметомёт, помощник для составления смет видеопродакшна.

📝 *Как пользоваться:*
Опиши проект текстом или 🎤 *голосовым сообщением*:

_"Рекламный ролик для ресторана. 2 съёмочных дня, 3 актёра, хронометраж 1 минута. Уровень 2, наценка 35%."_

📊 *Команды:*
/start — начать сначала
/excel — скачать текущую смету в Excel

Начинай! 👇"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс диалога"""
    context.user_data['conversation'] = []
    context.user_data['current_estimate_id'] = None
    context.user_data['edit_mode'] = False
    await update.message.reply_text("🔄 Диалог сброшен. Опиши новый проект!")


def get_estimate_keyboard(estimate_id: str) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопками для сметы"""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Внести правки", callback_data=f"edit:{estimate_id}"),
        ],
        [
            InlineKeyboardButton("📥 Полная смета", callback_data=f"excel:{estimate_id}"),
            InlineKeyboardButton("📤 Для клиента", callback_data=f"client_excel:{estimate_id}"),
        ],
        [
            InlineKeyboardButton("🆕 Новая смета", callback_data="new_estimate"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("edit:"):
        estimate_id = data.split(":")[1]
        
        if estimate_id in estimates_storage:
            context.user_data['current_estimate_id'] = estimate_id
            context.user_data['edit_mode'] = True
            context.user_data['conversation'] = []
            
            estimate = estimates_storage[estimate_id]
            project_name = estimate.get('project_name', 'Смета')
            
            await query.message.reply_text(
                f"✏️ *Режим редактирования*\n\n"
                f"Редактируем: _{project_name}_\n\n"
                f"Напиши или 🎤 надиктуй, что нужно изменить:\n"
                f"• _\"убери монтаж\"_\n"
                f"• _\"добавь ещё актёра\"_\n"
                f"• _\"наценку на графику сделай 50%\"_",
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text("❌ Смета не найдена. Создай новую.")
    
    elif data.startswith("excel:"):
        estimate_id = data.split(":")[1]
        
        if estimate_id in estimates_storage:
            estimate = estimates_storage[estimate_id]
            await send_excel_file(query.message, estimate, client_mode=False)
        else:
            await query.message.reply_text("❌ Смета не найдена.")
    
    elif data.startswith("client_excel:"):
        estimate_id = data.split(":")[1]
        
        if estimate_id in estimates_storage:
            estimate = estimates_storage[estimate_id]
            await send_excel_file(query.message, estimate, client_mode=True)
        else:
            await query.message.reply_text("❌ Смета не найдена.")
    
    elif data == "new_estimate":
        context.user_data['conversation'] = []
        context.user_data['current_estimate_id'] = None
        context.user_data['edit_mode'] = False
        
        await query.message.reply_text(
            "🆕 *Новая смета*\n\nОпиши проект текстом или голосом:",
            parse_mode='Markdown'
        )


async def send_excel_file(message, estimate: dict, client_mode: bool = False):
    """Отправляет Excel файл"""
    await message.chat.send_action("upload_document")
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            generate_estimate_excel(estimate, tmp.name, client_mode=client_mode)
            
            project_name = estimate.get('project_name', 'Смета')
            safe_name = "".join(c for c in project_name if c.isalnum() or c in ' -_')[:50]
            
            if client_mode:
                filename = f"{safe_name} (для клиента).xlsx"
                caption = "📤 Смета для клиента готова!"
            else:
                filename = f"{safe_name}.xlsx"
                caption = "📊 Полная смета готова!"
            
            with open(tmp.name, 'rb') as f:
                await message.reply_document(
                    document=f,
                    filename=filename,
                    caption=caption
                )
            
            os.unlink(tmp.name)
            
    except Exception as e:
        logger.error(f"Error generating Excel: {e}")
        await message.reply_text("❌ Ошибка при создании файла.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голосовых сообщений"""
    voice = update.message.voice
    
    await update.message.chat.send_action("typing")
    
    try:
        # Скачиваем голосовое сообщение
        voice_file = await context.bot.get_file(voice.file_id)
        
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
            await voice_file.download_to_drive(tmp.name)
            
            # Транскрибируем
            text = await transcribe_voice(tmp.name)
            os.unlink(tmp.name)
        
        # Показываем распознанный текст
        await update.message.reply_text(
            f"🎤 Распознано:\n_{text}_",
            parse_mode='Markdown'
        )
        
        # Обрабатываем как обычное текстовое сообщение
        await process_user_message(update, context, text)
        
    except Exception as e:
        logger.error(f"Error processing voice: {e}")
        await update.message.reply_text(
            "❌ Не удалось распознать голосовое сообщение. Попробуй ещё раз или напиши текстом."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_message = update.message.text
    await process_user_message(update, context, user_message)


async def process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    """Общая логика обработки сообщения (текст или распознанный голос)"""
    
    if 'conversation' not in context.user_data:
        context.user_data['conversation'] = []
    
    edit_mode = context.user_data.get('edit_mode', False)
    current_estimate_id = context.user_data.get('current_estimate_id')
    
    # Получаем текущую смету для редактирования
    current_estimate = None
    if current_estimate_id and current_estimate_id in estimates_storage:
        current_estimate = estimates_storage[current_estimate_id]
    
    # Формируем сообщение для AI
    if edit_mode and current_estimate:
        message_for_ai = f"[РЕЖИМ РЕДАКТИРОВАНИЯ]\n\nПравки от пользователя: {user_message}\n\n[ТЕКУЩАЯ СМЕТА для редактирования]:\n{json.dumps(current_estimate, ensure_ascii=False, indent=2)}"
        messages_for_ai = [{"role": "user", "content": message_for_ai}]
    else:
        context.user_data['conversation'].append({
            "role": "user",
            "content": user_message
        })
        messages_for_ai = context.user_data['conversation']
    
    await update.message.chat.send_action("typing")
    
    try:
        result = analyze_project(messages_for_ai)
        
        if result.get('ready') and result.get('estimate'):
            estimate = result['estimate']
            
            if edit_mode and current_estimate_id:
                estimate_id = current_estimate_id
                estimates_storage[estimate_id] = estimate
            else:
                estimate_id = generate_estimate_id()
                estimates_storage[estimate_id] = estimate
            
            context.user_data['current_estimate_id'] = estimate_id
            context.user_data['edit_mode'] = False
            
            context.user_data['conversation'] = [{
                "role": "assistant",
                "content": f"Смета создана: {estimate.get('project_name')}"
            }]
            
            formatted = format_estimate_text(estimate)
            
            if edit_mode:
                header = "✏️ *Смета обновлена!*\n\n"
            else:
                header = "✅ *Смета готова!*\n\n"
            
            await update.message.reply_text(
                header + formatted,
                parse_mode='Markdown',
                reply_markup=get_estimate_keyboard(estimate_id)
            )
        else:
            if not edit_mode:
                context.user_data['conversation'].append({
                    "role": "assistant",
                    "content": result['text_response']
                })
            await update.message.reply_text(result['text_response'])
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуй ещё раз или напиши /start для сброса."
        )


async def send_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка текущей сметы в Excel"""
    current_estimate_id = context.user_data.get('current_estimate_id')
    
    if current_estimate_id and current_estimate_id in estimates_storage:
        estimate = estimates_storage[current_estimate_id]
        await send_excel_file(update.message, estimate)
    else:
        await update.message.reply_text(
            "📭 Пока нет готовой сметы. Сначала опиши проект!"
        )


def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен!")
        print("Создай файл .env с содержимым:")
        print("TELEGRAM_BOT_TOKEN=твой_токен")
        print("OPENAI_API_KEY=твой_ключ")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("excel", send_excel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
