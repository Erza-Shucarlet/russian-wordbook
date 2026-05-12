"""
俄语单词本 — 数据库层
SQLite 存储单词、句式及答题统计
"""

import sqlite3
import os
import json
import sys

# PyInstaller 打包后使用 ~/.russian-wordbook/ 存放数据，保证持久化
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.join(os.path.expanduser('~'), '.russian-wordbook')
else:
    _BASE_DIR = os.path.dirname(__file__)

DB_PATH = os.path.join(_BASE_DIR, 'data', 'wordbook.db')
SETTINGS_PATH = os.path.join(_BASE_DIR, 'settings.json')


# ─── Schema 版本与迁移 ──────────────────────────────────────────

# 每次修改数据库结构后递增此版本号，并添加对应的迁移函数
_CURRENT_SCHEMA_VERSION = 1

# 迁移函数注册表: {目标版本: 迁移函数(conn)}
# 迁移函数只负责改表结构，不操作数据
_MIGRATIONS = {
    # 示例：将来版本 2 加字段时取消注释：
    # 2: lambda conn: conn.execute("ALTER TABLE words ADD COLUMN notes TEXT DEFAULT ''"),
}


def _ensure_meta_table(conn):
    """确保 meta 表存在（最早执行，不能依赖迁移）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)


def _get_schema_version(conn) -> int:
    """读取当前数据库版本号"""
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return int(row['value']) if row else 0


def _run_migrations(conn):
    """按顺序执行所有待执行的迁移"""
    current = _get_schema_version(conn)
    target = _CURRENT_SCHEMA_VERSION

    for version in range(current + 1, target + 1):
        if version in _MIGRATIONS:
            _MIGRATIONS[version](conn)

    # 更新版本号
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(target),))


def get_conn():
    """获取数据库连接，自动创建目录"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表（支持版本升级，不破坏已有数据）"""
    conn = get_conn()
    _ensure_meta_table(conn)

    # 检查是否为全新数据库
    words_exist = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='words'"
    ).fetchone() is not None

    if not words_exist:
        # 全新数据库：创建初始表结构
        conn.executescript("""
            CREATE TABLE words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                russian TEXT NOT NULL UNIQUE,
                russian_lower TEXT NOT NULL,
                chinese TEXT NOT NULL DEFAULT '',
                examples TEXT NOT NULL DEFAULT '[]',
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                corrected TEXT NOT NULL DEFAULT '',
                chinese TEXT NOT NULL DEFAULT '',
                examples TEXT NOT NULL DEFAULT '[]',
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX idx_words_russian_lower ON words(russian_lower);
            CREATE INDEX idx_sentences_corrected ON sentences(corrected);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(_CURRENT_SCHEMA_VERSION),)
        )

    _run_migrations(conn)
    conn.commit()
    conn.close()


# ─── 单词 CRUD ────────────────────────────────────────────────

def add_word(russian: str, chinese: str, examples: list) -> int:
    """添加单词，返回 id"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO words (russian, russian_lower, chinese, examples) VALUES (?, ?, ?, ?)",
            (russian.strip(), russian.strip().lower(), chinese.strip(), json.dumps(examples, ensure_ascii=False))
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # 单词已存在
    finally:
        conn.close()


def get_words(search: str = None, limit: int = 200) -> list:
    """获取单词列表，支持搜索"""
    conn = get_conn()
    if search:
        q = f"%{search.lower()}%"
        rows = conn.execute(
            "SELECT * FROM words WHERE russian_lower LIKE ? OR chinese LIKE ? ORDER BY russian LIMIT ?",
            (q, q, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM words ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_word(word_id: int) -> bool:
    """删除单词"""
    conn = get_conn()
    conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


def word_exists(russian: str) -> bool:
    """检查单词是否已存在"""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM words WHERE russian_lower = ?", (russian.strip().lower(),)
    ).fetchone()
    conn.close()
    return row is not None


# ─── 句式 CRUD ────────────────────────────────────────────────

def add_sentence(original: str, corrected: str, chinese: str, examples: list) -> int:
    """添加句式，返回 id"""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO sentences (original, corrected, chinese, examples) VALUES (?, ?, ?, ?)",
        (original.strip(), corrected.strip(), chinese.strip(), json.dumps(examples, ensure_ascii=False))
    )
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def get_sentences(search: str = None, limit: int = 200) -> list:
    """获取句式列表，支持搜索"""
    conn = get_conn()
    if search:
        q = f"%{search.lower()}%"
        rows = conn.execute(
            "SELECT * FROM sentences WHERE LOWER(original) LIKE ? OR LOWER(corrected) LIKE ? OR chinese LIKE ? ORDER BY id DESC LIMIT ?",
            (q, q, q, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sentences ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_sentence(sent_id: int) -> bool:
    """删除句式"""
    conn = get_conn()
    conn.execute("DELETE FROM sentences WHERE id = ?", (sent_id,))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


# ─── 答题统计 ─────────────────────────────────────────────────

def record_answer(table: str, item_id: int, is_correct: bool):
    """记录答题结果"""
    conn = get_conn()
    col = "correct_count" if is_correct else "wrong_count"
    conn.execute(f"UPDATE {table} SET {col} = {col} + 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """获取统计信息"""
    conn = get_conn()
    total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    total_sentences = conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]
    conn.close()
    return {
        "total_words": total_words,
        "total_sentences": total_sentences,
    }


def get_all_items() -> dict:
    """获取所有可用于复习的条目"""
    conn = get_conn()
    words = conn.execute("SELECT * FROM words").fetchall()
    sentences = conn.execute("SELECT * FROM sentences").fetchall()
    conn.close()
    return {
        "words": [_row_to_dict(r) for r in words],
        "sentences": [_row_to_dict(r) for r in sentences],
    }


# ─── 工具 ─────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if 'examples' in d and isinstance(d['examples'], str):
        try:
            d['examples'] = json.loads(d['examples'])
        except json.JSONDecodeError:
            d['examples'] = []
    return d