#!/usr/bin/env python3
"""Точка входа для запуска бота"""

import os

# Защита от случайного локального запуска
# На Railway есть переменная RAILWAY_ENVIRONMENT
# Локально можно запустить с LOCAL_RUN=1 если очень нужно
if not os.getenv("RAILWAY_ENVIRONMENT") and not os.getenv("LOCAL_RUN"):
    print("⚠️  Локальный запуск заблокирован!")
    print("Бот уже работает на Railway.")
    print("")
    print("Если нужно запустить локально для тестов:")
    print("  LOCAL_RUN=1 python3 run.py")
    exit(0)

from bot.main import main

if __name__ == "__main__":
    main()
