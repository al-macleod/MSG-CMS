"""SQLite persistence for the academic workspace.

The UI communicates with this module through DatabaseWorker signals. Keeping
SQL here makes schema changes and alternate storage backends easier to test.
"""

import os
import sqlite3
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_cms_data.db")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db(conn=None):
    owns = conn is None
    conn = conn or sqlite3.connect(DB_FILE, timeout=10)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER, title TEXT NOT NULL,
            category TEXT NOT NULL, content TEXT, tags TEXT, editor_mode TEXT DEFAULT 'rich',
            updated_at TEXT, created_at TEXT, FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1), first_name TEXT, dob TEXT, email TEXT,
            gender TEXT, hobbies TEXT, employment TEXT, goals TEXT, mental_health TEXT,
            ai_name TEXT, system_prompt TEXT, persona TEXT, memory_enabled INTEGER DEFAULT 1,
            ollama_url TEXT DEFAULT 'http://127.0.0.1:11434', ollama_model TEXT DEFAULT 'llama3.2',
            onboarding_complete INTEGER DEFAULT 0
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    for column, definition in (("editor_mode", "TEXT DEFAULT 'rich'"), ("created_at", "TEXT")):
        try:
            cur.execute(f"ALTER TABLE notes ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass
    if cur.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
        cur.executemany("INSERT INTO courses (code, name) VALUES (?, ?)", [
            ("GENERAL", "General & Miscellaneous"),
            ("TERM-1", "Term 1 Materials"),
            ("TERM-2", "Term 2 Materials"),
        ])
    cur.execute(
        "INSERT OR IGNORE INTO profile (id, system_prompt, persona) VALUES (1, ?, ?)",
        ("You are a helpful, privacy-conscious academic copilot. Be concise, honest, and safe.",
         "A calm, practical study partner"),
    )
    conn.commit()
    if owns:
        conn.close()


class DatabaseWorker(QObject):
    request = pyqtSignal(str, object)
    result = pyqtSignal(str, object)
    error = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.conn = None

    @pyqtSlot(str, object)
    def execute(self, operation, payload):
        try:
            if operation == "initialize":
                self.conn = sqlite3.connect(DB_FILE, timeout=10)
                init_db(self.conn)
                self.result.emit(operation, None)
                return
            cur = self.conn.cursor()
            if operation == "profile":
                cur.execute(
                    "SELECT first_name,dob,email,gender,hobbies,employment,goals,mental_health,"
                    "ai_name,system_prompt,persona,memory_enabled,ollama_url,ollama_model,"
                    "onboarding_complete FROM profile WHERE id=1"
                )
                self.result.emit(operation, cur.fetchone())
            elif operation == "save_profile":
                cur.execute(
                    """UPDATE profile SET first_name=?,dob=?,email=?,gender=?,hobbies=?,employment=?,goals=?,
                    mental_health=?,ai_name=?,system_prompt=?,persona=?,memory_enabled=?,ollama_url=?,ollama_model=?,
                    onboarding_complete=1 WHERE id=1""",
                    payload,
                )
                self.conn.commit()
                self.result.emit(operation, None)
            elif operation == "courses":
                cur.execute("SELECT id,code,name FROM courses ORDER BY code")
                self.result.emit(operation, cur.fetchall())
            elif operation == "tree":
                query = (payload or "").lower().strip()
                cur.execute(
                    """SELECT n.id,n.title,n.category,n.updated_at,c.code FROM notes n
                    LEFT JOIN courses c ON c.id=n.course_id
                    WHERE ?='' OR lower(n.title||' '||coalesce(n.content,'')||' '||coalesce(n.tags,'')) LIKE ?
                    ORDER BY n.updated_at DESC""",
                    (query, f"%{query}%"),
                )
                self.result.emit(operation, cur.fetchall())
            elif operation == "note":
                cur.execute(
                    """SELECT n.id,n.course_id,n.title,n.category,n.content,n.tags,n.editor_mode,n.updated_at,
                    coalesce(c.code,'') FROM notes n LEFT JOIN courses c ON c.id=n.course_id WHERE n.id=?""",
                    (payload,),
                )
                self.result.emit(operation, cur.fetchone())
            elif operation == "save_note":
                note_id, course_id, title, category, content, tags, mode = payload
                timestamp = now()
                if note_id:
                    cur.execute(
                        "UPDATE notes SET course_id=?,title=?,category=?,content=?,tags=?,editor_mode=?,updated_at=? WHERE id=?",
                        (course_id, title, category, content, tags, mode, timestamp, note_id),
                    )
                else:
                    cur.execute(
                        """INSERT INTO notes(course_id,title,category,content,tags,editor_mode,updated_at,created_at)
                        VALUES(?,?,?,?,?,?,?,?)""",
                        (course_id, title, category, content, tags, mode, timestamp, timestamp),
                    )
                    note_id = cur.lastrowid
                self.conn.commit()
                self.result.emit(operation, (note_id, timestamp))
            elif operation == "delete_note":
                cur.execute("DELETE FROM notes WHERE id=?", (payload,))
                self.conn.commit()
                self.result.emit(operation, None)
            elif operation == "analytics":
                cur.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(content)),0), COUNT(DISTINCT course_id) FROM notes")
                totals = cur.fetchone()
                cur.execute("SELECT category,COUNT(*) FROM notes GROUP BY category ORDER BY COUNT(*) DESC")
                categories = cur.fetchall()
                cur.execute(
                    "SELECT substr(updated_at,1,10),COUNT(*) FROM notes WHERE updated_at IS NOT NULL "
                    "GROUP BY substr(updated_at,1,10) ORDER BY substr(updated_at,1,10) DESC LIMIT 7"
                )
                self.result.emit(operation, (totals, categories, cur.fetchall()))
            elif operation == "chat_history":
                cur.execute("SELECT role,content,created_at FROM chat_messages ORDER BY id")
                self.result.emit(operation, cur.fetchall())
            elif operation == "save_chat":
                cur.execute("INSERT INTO chat_messages(role,content,created_at) VALUES(?,?,?)",
                            (payload[0], payload[1], now()))
                self.conn.commit()
                self.result.emit(operation, None)
        except Exception as exc:
            self.error.emit(operation, str(exc))
