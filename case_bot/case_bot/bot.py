"""Симулятор кейсов для Telegram (aiogram 3 + SQLite).
Только виртуальная валюта: без пополнения и без вывода.
"""
import asyncio
import os
import random
import time

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardMarkup, MenuButtonWebApp,
                           Message, WebAppInfo)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from cases import CASES, RARITIES

DB_PATH = "bot.db"
START_BALANCE = 1000
DAILY_BONUS = 500
DAILY_COOLDOWN = 24 * 3600
PAGE_SIZE = 6
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

router = Router()
rng = random.SystemRandom()
lock = asyncio.Lock()  # чтобы баланс не уходил в минус при быстрых нажатиях
db: aiosqlite.Connection


# ---------- база данных ----------
async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    await db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            balance INTEGER NOT NULL,
            last_daily INTEGER NOT NULL DEFAULT 0)"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            price INTEGER NOT NULL)"""
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_inv_user ON inventory(user_id)")
    await db.commit()


async def ensure_user(user) -> int:
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, name, balance) VALUES (?, ?, ?)",
        (user.id, user.full_name, START_BALANCE),
    )
    await db.execute("UPDATE users SET name=? WHERE user_id=?", (user.full_name, user.id))
    await db.commit()
    cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (user.id,))
    return (await cur.fetchone())[0]


async def get_balance(uid: int) -> int:
    cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = await cur.fetchone()
    return row[0] if row else 0


# ---------- логика дропа ----------
def roll(case: dict) -> dict:
    rarities = list(RARITIES.keys())
    weights = [RARITIES[r]["weight"] for r in rarities]
    rarity = rng.choices(rarities, weights=weights, k=1)[0]
    pool = [i for i in case["items"] if i["rarity"] == rarity]
    return rng.choice(pool)


# ---------- клавиатуры и помощники ----------
def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if WEBAPP_URL:
        kb.button(text="🎮 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text="📦 Кейсы", callback_data="cases")
    kb.button(text="🎒 Инвентарь", callback_data="inv:0")
    kb.button(text="🎁 Бонус", callback_data="daily")
    kb.button(text="🏆 Топ", callback_data="top")
    kb.adjust(1, 2, 2) if WEBAPP_URL else kb.adjust(2)
    return kb.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu")
    return kb.as_markup()


async def safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass  # текст не изменился


async def menu_text(uid: int) -> str:
    return (
        "🎰 Симулятор кейсов\n"
        f"💰 Баланс: {await get_balance(uid)} монет\n\n"
        "Монеты виртуальные: пополнения и вывода нет."
    )


# ---------- команды ----------
@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message):
    await ensure_user(message.from_user)
    await message.answer(await menu_text(message.from_user.id), reply_markup=main_menu())


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery):
    await ensure_user(cb.from_user)
    await safe_edit(cb, await menu_text(cb.from_user.id), main_menu())
    await cb.answer()


# ---------- кейсы ----------
@router.callback_query(F.data == "cases")
async def cb_cases(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    for cid, case in CASES.items():
        kb.button(text=f"{case['name']} - {case['price']} 💰", callback_data=f"case:{cid}")
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    await safe_edit(cb, "📦 Выбери кейс:", kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("case:"))
async def cb_case(cb: CallbackQuery):
    case = CASES.get(cb.data.split(":")[1])
    if not case:
        await cb.answer("Кейс не найден", show_alert=True)
        return
    cid = cb.data.split(":")[1]
    total = sum(r["weight"] for r in RARITIES.values())
    lines = [f"📦 {case['name']} - {case['price']} 💰", "", "Шансы:"]
    for key, r in RARITIES.items():
        lines.append(f"{r['emoji']} {r['title']}: {r['weight'] / total * 100:.2f}%")
    lines.append("")
    lines.append(f"💰 Баланс: {await get_balance(cb.from_user.id)}")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔓 Открыть", callback_data=f"open:{cid}")
    kb.button(text="⬅️ Назад", callback_data="cases")
    kb.adjust(1)
    await safe_edit(cb, "\n".join(lines), kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("open:"))
async def cb_open(cb: CallbackQuery):
    cid = cb.data.split(":")[1]
    case = CASES.get(cid)
    if not case:
        await cb.answer("Кейс не найден", show_alert=True)
        return
    async with lock:
        await ensure_user(cb.from_user)
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (case["price"], cb.from_user.id, case["price"]),
        )
        if cur.rowcount == 0:
            await db.rollback()
            await cb.answer("Не хватает монет. Забери бонус в меню 🎁", show_alert=True)
            return
        drop = roll(case)
        await db.execute(
            "INSERT INTO inventory (user_id, item_name, rarity, price) VALUES (?, ?, ?, ?)",
            (cb.from_user.id, drop["name"], drop["rarity"], drop["price"]),
        )
        await db.commit()
        balance = await get_balance(cb.from_user.id)

    r = RARITIES[drop["rarity"]]
    text = (
        f"📦 {case['name']}\n\n"
        f"{r['emoji']} {drop['name']}\n"
        f"{r['title']} - стоимость {drop['price']} 💰\n\n"
        f"💰 Баланс: {balance}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🔓 Ещё раз ({case['price']} 💰)", callback_data=f"open:{cid}")
    kb.button(text="🎒 Инвентарь", callback_data="inv:0")
    kb.button(text="⬅️ К кейсам", callback_data="cases")
    kb.adjust(1)
    await safe_edit(cb, text, kb.as_markup())
    await cb.answer()


# ---------- инвентарь ----------
@router.callback_query(F.data.startswith("inv:"))
async def cb_inventory(cb: CallbackQuery):
    page = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    await ensure_user(cb.from_user)

    cur = await db.execute(
        "SELECT COUNT(*), COALESCE(SUM(price), 0) FROM inventory WHERE user_id=?", (uid,)
    )
    count, value = await cur.fetchone()
    if count == 0:
        await safe_edit(cb, "🎒 Инвентарь пуст. Открой кейс!", back_kb())
        await cb.answer()
        return

    pages = (count - 1) // PAGE_SIZE + 1
    page = max(0, min(page, pages - 1))
    cur = await db.execute(
        "SELECT id, item_name, rarity, price FROM inventory WHERE user_id=? "
        "ORDER BY price DESC, id DESC LIMIT ? OFFSET ?",
        (uid, PAGE_SIZE, page * PAGE_SIZE),
    )
    rows = await cur.fetchall()

    kb = InlineKeyboardBuilder()
    for item_id, name, rarity, price in rows:
        kb.button(
            text=f"{RARITIES[rarity]['emoji']} {name} - продать за {price}",
            callback_data=f"sell:{item_id}",
        )
    kb.adjust(1)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="◀️", callback_data=f"inv:{page - 1}")
    nav.button(text=f"{page + 1}/{pages}", callback_data="noop")
    if page < pages - 1:
        nav.button(text="▶️", callback_data=f"inv:{page + 1}")
    kb.attach(nav)

    extra = InlineKeyboardBuilder()
    extra.button(text="💸 Продать всё дешёвое (синие и фиолетовые)", callback_data="sellcheap")
    extra.button(text="⬅️ В меню", callback_data="menu")
    extra.adjust(1)
    kb.attach(extra)

    text = f"🎒 Инвентарь: {count} шт., общая стоимость {value} 💰"
    await safe_edit(cb, text, kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("sell:"))
async def cb_sell(cb: CallbackQuery):
    item_id = int(cb.data.split(":")[1])
    async with lock:
        cur = await db.execute(
            "SELECT price FROM inventory WHERE id=? AND user_id=?", (item_id, cb.from_user.id)
        )
        row = await cur.fetchone()
        if not row:
            await cb.answer("Предмет уже продан", show_alert=True)
        else:
            await db.execute("DELETE FROM inventory WHERE id=?", (item_id,))
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?", (row[0], cb.from_user.id)
            )
            await db.commit()
            await cb.answer(f"Продано за {row[0]} 💰")
    cb.data = "inv:0"
    await cb_inventory(cb)


@router.callback_query(F.data == "sellcheap")
async def cb_sell_cheap(cb: CallbackQuery):
    async with lock:
        cur = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(price), 0) FROM inventory "
            "WHERE user_id=? AND rarity IN ('milspec', 'restricted')",
            (cb.from_user.id,),
        )
        count, total = await cur.fetchone()
        if count == 0:
            await cb.answer("Дешёвых предметов нет", show_alert=True)
            return
        await db.execute(
            "DELETE FROM inventory WHERE user_id=? AND rarity IN ('milspec', 'restricted')",
            (cb.from_user.id,),
        )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?", (total, cb.from_user.id)
        )
        await db.commit()
    await cb.answer(f"Продано {count} шт. за {total} 💰", show_alert=True)
    cb.data = "inv:0"
    await cb_inventory(cb)


# ---------- бонус и топ ----------
@router.callback_query(F.data == "daily")
async def cb_daily(cb: CallbackQuery):
    now = int(time.time())
    async with lock:
        await ensure_user(cb.from_user)
        cur = await db.execute("SELECT last_daily FROM users WHERE user_id=?", (cb.from_user.id,))
        last = (await cur.fetchone())[0]
        wait = last + DAILY_COOLDOWN - now
        if wait > 0:
            h, m = wait // 3600, (wait % 3600) // 60
            await cb.answer(f"Бонус уже забран. Следующий через {h} ч {m} мин", show_alert=True)
            return
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_daily = ? WHERE user_id=?",
            (DAILY_BONUS, now, cb.from_user.id),
        )
        await db.commit()
    await cb.answer(f"+{DAILY_BONUS} 💰 Приходи завтра!", show_alert=True)
    await safe_edit(cb, await menu_text(cb.from_user.id), main_menu())


@router.callback_query(F.data == "top")
async def cb_top(cb: CallbackQuery):
    cur = await db.execute(
        """SELECT u.name, u.balance + COALESCE(SUM(i.price), 0) AS total
           FROM users u LEFT JOIN inventory i ON i.user_id = u.user_id
           GROUP BY u.user_id ORDER BY total DESC LIMIT 10"""
    )
    rows = await cur.fetchall()
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    lines = ["🏆 Топ по богатству (баланс + инвентарь):", ""]
    for i, (name, total) in enumerate(rows):
        lines.append(f"{medals[i]} {name}: {total} 💰")
    await safe_edit(cb, "\n".join(lines), back_kb())
    await cb.answer()


# ---------- запуск ----------
async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Задай токен: переменная окружения BOT_TOKEN")
    await init_db()
    bot = Bot(token)
    if WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Играть", web_app=WebAppInfo(url=WEBAPP_URL))
        )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
