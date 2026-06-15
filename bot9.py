import random
import json
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# 👇 ВСТАВЬТЕ ВАШ ТОКЕН ОТ @BotFather
BOT_TOKEN = "ВАШ_ТОКЕН"

# Файл для сохранения ошибок
MISTAKES_FILE = "user_mistakes.json"

class TrainingState(StatesGroup):
    waiting_for_answer = State()

# Загружаем словарь
with open("words9.json", "r", encoding="utf-8") as f:
    WORDS = json.load(f)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Функция загрузки ошибок из файла
def load_mistakes():
    if os.path.exists(MISTAKES_FILE):
        try:
            with open(MISTAKES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# Функция сохранения ошибок в файл
def save_mistakes(data):
    with open(MISTAKES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Загружаем сохранённые ошибки при старте
user_stats = load_mistakes()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "total": 0, "mistakes": {}}
        save_mistakes(user_stats)
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("🎯 Начать тренировку"),
        KeyboardButton("📊 Статистика")
    )
    keyboard.add(
        KeyboardButton("❌ Мои ошибки"),
        KeyboardButton("🗑 Очистить ошибки")
    )
    await message.answer(
        "📚 *Бот для подготовки к заданию №9 ЕГЭ по русскому языку*\n\n"
        "📝 *Правописание корней* (непроверяемые гласные)\n\n"
        f"📖 В базе {len(WORDS)} слов\n\n"
        "Я показываю слово с пропуском. Выберите правильную букву!\n\n"
        "🔹 «Начать тренировку» — приступаем\n"
        "🔹 «Мои ошибки» — список слов, в которых вы ошиблись\n"
        "🔹 «Очистить ошибки» — удалить все ошибки из копилки\n"
        "🔹 «Статистика» — ваши успехи\n\n"
        "✅ *Ваши ошибки сохраняются даже после перезапуска бота!*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(lambda msg: msg.text == "🎯 Начать тренировку")
async def new_question(message: types.Message, state: FSMContext):
    await send_question(message.chat.id, state)

@dp.message_handler(lambda msg: msg.text == "📊 Статистика")
async def show_stats(message: types.Message):
    user_id = str(message.from_user.id)
    stats = user_stats.get(user_id, {"correct": 0, "total": 0, "mistakes": {}})
    
    if stats["total"] > 0:
        percent = (stats["correct"] / stats["total"]) * 100
        await message.answer(
            f"📊 *Ваша статистика*\n\n"
            f"✅ Правильно: {stats['correct']}\n"
            f"❌ Неправильно: {stats['total'] - stats['correct']}\n"
            f"📈 Точность: {percent:.1f}%\n\n"
            f"📝 Слов в копилке ошибок: {len(stats['mistakes'])}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("📊 Пока нет попыток. Начните тренировку!")

@dp.message_handler(lambda msg: msg.text == "❌ Мои ошибки")
async def show_mistakes(message: types.Message):
    user_id = str(message.from_user.id)
    stats = user_stats.get(user_id, {"correct": 0, "total": 0, "mistakes": {}})
    
    mistakes = stats.get("mistakes", {})
    
    if not mistakes:
        await message.answer(
            "✅ *В копилке ошибок пока пусто!*\n\n"
            "Продолжайте тренировку — все слова запоминаются правильно!",
            parse_mode="Markdown"
        )
        return
    
    mistake_list = []
    for word, correct_letter in mistakes.items():
        word_data = WORDS.get(word, {})
        word_with_gap = word_data.get("word_with_gap", word)
        word_correct = word_with_gap.replace("...", f"*{correct_letter.upper()}*")
        mistake_list.append(f"• {word_correct}")
    
    result = "📝 *Ваши ошибки (слова для повторения):*\n\n" + "\n".join(mistake_list)
    result += f"\n\n📊 *Всего слов в копилке:* {len(mistakes)}"
    result += "\n\n💡 *Совет:* правильно ответите на слово — оно удалится из ошибок!"
    
    await message.answer(result, parse_mode="Markdown")

@dp.message_handler(lambda msg: msg.text == "🗑 Очистить ошибки")
async def clear_mistakes(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "total": 0, "mistakes": {}}
    
    old_count = len(user_stats[user_id]["mistakes"])
    user_stats[user_id]["mistakes"] = {}
    save_mistakes(user_stats)
    
    await message.answer(
        f"🗑 *Копилка ошибок очищена!*\n\n"
        f"Было удалено слов: {old_count}\n\n"
        f"Продолжайте тренировку! 💪",
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("answer_"), state=TrainingState.waiting_for_answer)
async def check_answer(callback_query: types.CallbackQuery, state: FSMContext):
    user_answer = callback_query.data.replace("answer_", "")
    
    async with state.proxy() as data:
        word = data.get('word')
        word_with_gap = data.get('word_with_gap')
        correct = data.get('correct')
    
    user_id = str(callback_query.from_user.id)
    
    if user_id not in user_stats:
        user_stats[user_id] = {"correct": 0, "total": 0, "mistakes": {}}
    
    word_with_correct = word_with_gap.replace("...", f"*{correct.upper()}*")
    word_with_wrong = word_with_gap.replace("...", f"*{user_answer.upper()}*")
    
    if user_answer.lower() == correct.lower():
        await callback_query.answer("✅ Правильно!", show_alert=True)
        await callback_query.message.edit_text(
            f"✅ *Верно!*\n\n"
            f"Слово: {word_with_correct}\n\n"
            f"➡️ Следующий вопрос...",
            parse_mode="Markdown"
        )
        user_stats[user_id]["correct"] += 1
        
        if word in user_stats[user_id]["mistakes"]:
            del user_stats[user_id]["mistakes"][word]
            await callback_query.message.answer(
                f"🎉 *Отлично!* Слово «{word}» удалено из копилки ошибок!",
                parse_mode="Markdown"
            )
    else:
        await callback_query.answer(f"❌ Неправильно! Правильная буква: {correct.upper()}", show_alert=True)
        await callback_query.message.edit_text(
            f"❌ *Неправильно*\n\n"
            f"Вы выбрали: {word_with_wrong}\n"
            f"✅ Правильно: {word_with_correct}\n\n"
            f"📝 *Слово добавлено в копилку ошибок!*\n\n"
            f"➡️ Следующий вопрос...",
            parse_mode="Markdown"
        )
        user_stats[user_id]["mistakes"][word] = correct
    
    user_stats[user_id]["total"] += 1
    save_mistakes(user_stats)
    
    await asyncio.sleep(1.5)
    await send_question(callback_query.message.chat.id, state)

async def send_question(chat_id, state: FSMContext):
    word_key = random.choice(list(WORDS.keys()))
    word_data = WORDS[word_key]
    
    word_with_gap = word_data["word_with_gap"]
    correct = word_data["correct_letter"]
    variants = word_data["variants"]
    
    shuffled_variants = random.sample(variants, len(variants))
    
    async with state.proxy() as data:
        data['word'] = word_key
        data['word_with_gap'] = word_with_gap
        data['correct'] = correct
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    for v in shuffled_variants:
        keyboard.add(InlineKeyboardButton(v.upper(), callback_data=f"answer_{v}"))
    
    await bot.send_message(
        chat_id,
        f"📝 *Вставьте пропущенную букву:*\n\n"
        f"`{word_with_gap}`\n\n"
        f"Выберите вариант:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(TrainingState.waiting_for_answer.state)

if __name__ == "__main__":
    print(f"✅ Бот для задания №9 запущен! В базе {len(WORDS)} слов")
    print(f"📁 Файл ошибок: {MISTAKES_FILE}")
    executor.start_polling(dp, skip_updates=True)