import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import settings

DB_PATH = "assistant_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Настройки пользователя
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                custom_prompt TEXT DEFAULT '',
                history_length INTEGER DEFAULT 8,
                language TEXT DEFAULT 'ru',
                response_delay INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # История диалогов в бизнес-чатах
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT NOT NULL,
                client_chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,           -- 'user' или 'assistant'
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для быстрого поиска
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_connection 
            ON chat_history(business_connection_id, client_chat_id, timestamp)
        """)
        
        await db.commit()

async def get_user_settings(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "user_id": row[0],
                "custom_prompt": row[1] or "",
                "history_length": row[2] or settings.DEFAULT_HISTORY_LENGTH,
                "language": row[3] or settings.DEFAULT_LANGUAGE,
                "response_delay": row[4] or settings.DEFAULT_DELAY,
            }
        else:
            # Создаём запись по умолчанию
            await db.execute(
                """INSERT INTO user_settings (user_id, custom_prompt, history_length, language, response_delay)
                   VALUES (?, '', ?, ?, ?)""",
                (user_id, settings.DEFAULT_HISTORY_LENGTH, settings.DEFAULT_LANGUAGE, settings.DEFAULT_DELAY)
            )
            await db.commit()
            return {
                "user_id": user_id,
                "custom_prompt": "",
                "history_length": settings.DEFAULT_HISTORY_LENGTH,
                "language": settings.DEFAULT_LANGUAGE,
                "response_delay": settings.DEFAULT_DELAY,
            }

async def update_user_prompt(user_id: int, prompt: str) -> bool:
    if len(prompt) > settings.MAX_PROMPT_LENGTH:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE user_settings 
               SET custom_prompt = ?, updated_at = CURRENT_TIMESTAMP 
               WHERE user_id = ?""",
            (prompt, user_id)
        )
        await db.commit()
        return True

async def update_user_setting(user_id: int, field: str, value: Any) -> bool:
    allowed_fields = ["history_length", "language", "response_delay"]
    if field not in allowed_fields:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"""UPDATE user_settings 
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?""",
            (value, user_id)
        )
        await db.commit()
        return True

async def add_message_to_history(
    business_connection_id: str, 
    client_chat_id: int, 
    role: str, 
    content: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO chat_history (business_connection_id, client_chat_id, role, content)
               VALUES (?, ?, ?, ?)""",
            (business_connection_id, client_chat_id, role, content)
        )
        await db.commit()

async def get_chat_history(
    business_connection_id: str, 
    client_chat_id: int, 
    limit: int = 10
) -> List[Dict[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT role, content FROM chat_history 
               WHERE business_connection_id = ? AND client_chat_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (business_connection_id, client_chat_id, limit)
        )
        rows = await cursor.fetchall()
        # Возвращаем в хронологическом порядке (старые -> новые)
        history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        return history

async def clear_chat_history(business_connection_id: str, client_chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM chat_history WHERE business_connection_id = ? AND client_chat_id = ?",
            (business_connection_id, client_chat_id)
        )
        await db.commit()