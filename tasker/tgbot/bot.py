"""Telegram-бот для управления задачами через Tasker API."""

from __future__ import annotations

import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE = os.getenv("TASKER_API_URL", "http://tasker_backend:8000")

# --- Router ---
router = Router()


# --- FSM States ---
class TaskStates(StatesGroup):
    waiting_for_task_text = State()
    waiting_for_edit_id = State()
    waiting_for_edit_text = State()
    waiting_for_delete_id = State()


# --- Helpers ---
def main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Новая задача"), KeyboardButton(text="📋 Мои задачи")],
            [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="🗑 Удалить")],
        ],
        resize_keyboard=True,
    )


def _user_id(message: types.Message) -> int:
    """Telegram user_id как user_id для API."""
    return message.from_user.id


async def api_request(method: str, path: str, **kwargs) -> dict | list | None:
    """Выполнить запрос к Tasker API."""
    url = f"{API_BASE}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, **kwargs) as resp:
            if resp.status >= 400:
                body = await resp.text()
                logger.error(f"API error {resp.status}: {body}")
                return None
            return await resp.json()


# --- Handlers ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для управления задачами.\n\n"
        "Используй кнопки ниже или команды:\n"
        "/new — создать задачу\n"
        "/list — список задач\n"
        "/edit — редактировать задачу\n"
        "/delete — удалить задачу",
        reply_markup=main_keyboard(),
    )


@router.message(Command("new"))
@router.message(F.text == "📝 Новая задача")
async def cmd_new_task(message: types.Message, state: FSMContext):
    await state.set_state(TaskStates.waiting_for_task_text)
    await message.answer(
        "✏️ Введи текст задачи.\n"
        "Можно указать дату/время, например:\n"
        "<i>Купить молоко завтра в 10:00</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(TaskStates.waiting_for_task_text)
async def process_new_task(message: types.Message, state: FSMContext):
    text = message.text.strip()
    result = await api_request(
        "POST",
        "/api/task",
        json={
            "user_id": _user_id(message),
            "text": text,
            "source": "telegram",
            "timezone": "Europe/Moscow",
        },
    )
    if result:
        due = result.get("due_at") or "не указано"
        await message.answer(
            f"✅ Задача создана!\n\n"
            f"<b>ID:</b> {result['task_id']}\n"
            f"<b>Название:</b> {result['title']}\n"
            f"<b>Срок:</b> {due}\n"
            f"<b>Статус:</b> {result['status']}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer("❌ Не удалось создать задачу. Проверь текст.", reply_markup=main_keyboard())
    await state.clear()


@router.message(Command("list"))
@router.message(F.text == "📋 Мои задачи")
async def cmd_list_tasks(message: types.Message):
    tasks = await api_request("GET", f"/api/tasks?user_id={_user_id(message)}&limit=20")
    if not tasks:
        await message.answer("📭 Задач пока нет.", reply_markup=main_keyboard())
        return

    status_emoji = {"todo": "⬜", "in_progress": "🔶", "done": "✅"}
    lines = []
    for t in tasks:
        emoji = status_emoji.get(t["status"], "❓")
        due = t.get("due_at") or ""
        due_str = f" 📅 {due}" if due else ""
        lines.append(f"{emoji} <b>[{t['task_id']}]</b> {t['title']}{due_str}")

    text = "📋 <b>Твои задачи:</b>\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())


@router.message(Command("edit"))
@router.message(F.text == "✏️ Редактировать")
async def cmd_edit_task(message: types.Message, state: FSMContext):
    await state.set_state(TaskStates.waiting_for_edit_id)
    await message.answer(
        "✏️ Введи ID задачи и новые данные через пробел.\n"
        "Формат: <code>ID статус</code>\n\n"
        "Статусы: <code>todo</code>, <code>in_progress</code>, <code>done</code>\n\n"
        "Пример: <code>5 done</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(TaskStates.waiting_for_edit_id)
async def process_edit_task(message: types.Message, state: FSMContext):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Формат: <code>ID статус</code>", parse_mode=ParseMode.HTML)
        return

    try:
        task_id = int(parts[0])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    new_status = parts[1].strip().lower()
    valid_statuses = {"todo", "in_progress", "done"}
    if new_status not in valid_statuses:
        await message.answer(
            f"❌ Неверный статус. Допустимые: {', '.join(valid_statuses)}"
        )
        return

    result = await api_request(
        "PUT",
        f"/api/tasks/{task_id}?user_id={_user_id(message)}",
        json={"status": new_status},
    )
    if result:
        await message.answer(
            f"✅ Задача [{task_id}] обновлена → <b>{new_status}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer("❌ Не удалось обновить задачу.", reply_markup=main_keyboard())
    await state.clear()


@router.message(Command("delete"))
@router.message(F.text == "🗑 Удалить")
async def cmd_delete_task(message: types.Message, state: FSMContext):
    await state.set_state(TaskStates.waiting_for_delete_id)
    await message.answer("🗑 Введи ID задачи для удаления:")


@router.message(TaskStates.waiting_for_delete_id)
async def process_delete_task(message: types.Message, state: FSMContext):
    try:
        task_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    result = await api_request(
        "DELETE",
        f"/api/tasks/{task_id}?user_id={_user_id(message)}",
    )
    if result:
        await message.answer(
            f"✅ Задача [{task_id}] удалена.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer("❌ Не удалось удалить задачу.", reply_markup=main_keyboard())
    await state.clear()


# --- Fallback ---
@router.message()
async def fallback(message: types.Message):
    await message.answer(
        "🤔 Не понял команду. Используй кнопки или /help",
        reply_markup=main_keyboard(),
    )


# --- Main ---
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан!")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
