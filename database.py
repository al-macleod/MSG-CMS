"""SQLite persistence for the academic workspace.

The UI communicates with this module through DatabaseWorker signals. Keeping
SQL here makes schema changes and alternate storage backends easier to test.
"""

import json
import os
import shutil
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
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER, title TEXT NOT NULL,
            description TEXT, due_date TEXT, priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open', created_at TEXT NOT NULL, completed_at TEXT,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER, title TEXT NOT NULL,
            url TEXT, description TEXT, tags TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS note_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL,
            title TEXT NOT NULL, content TEXT, saved_at TEXT NOT NULL,
            FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL,
            file_name TEXT NOT NULL, file_path TEXT NOT NULL, mime_type TEXT,
            file_size INTEGER DEFAULT 0, created_at TEXT NOT NULL,
            FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
        )"""
    )
    for column, definition in (
        ("editor_mode", "TEXT DEFAULT 'rich'"), ("created_at", "TEXT"),
        ("is_favorite", "INTEGER DEFAULT 0"), ("is_archived", "INTEGER DEFAULT 0"),
        ("reminder_at", "TEXT"),
    ):
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
            elif operation in ("courses", "courses_for_quick_add"):
                cur.execute("SELECT id,code,name FROM courses ORDER BY code")
                self.result.emit(operation, cur.fetchall())
            elif operation == "tree":
                query = (payload.get("query", "") if isinstance(payload, dict) else payload or "").lower().strip()
                include_archived = bool(payload.get("include_archived")) if isinstance(payload, dict) else False
                course_id = payload.get("course_id") if isinstance(payload, dict) else None
                cur.execute(
                    """SELECT n.id,n.title,n.category,n.updated_at,c.code FROM notes n
                    LEFT JOIN courses c ON c.id=n.course_id
                    WHERE (?='' OR lower(n.title||' '||coalesce(n.content,'')||' '||coalesce(n.tags,'')) LIKE ?)
                    AND (?=1 OR coalesce(n.is_archived,0)=0)
                    AND (? IS NULL OR n.course_id=?)
                    ORDER BY n.updated_at DESC""",
                    (query, f"%{query}%", int(include_archived), course_id, course_id),
                )
                self.result.emit(operation, cur.fetchall())
            elif operation == "note":
                cur.execute(
                    """SELECT n.id,n.course_id,n.title,n.category,n.content,n.tags,n.editor_mode,n.updated_at,
                    coalesce(c.code,'') FROM notes n LEFT JOIN courses c ON c.id=n.course_id WHERE n.id=?""",
                    (payload,),
                )
                self.result.emit(operation, cur.fetchone())
            elif operation == "course_overview":
                cur.execute("""SELECT c.id,c.code,c.name,COUNT(DISTINCT n.id),COUNT(DISTINCT t.id),
                    COUNT(DISTINCT r.id),COALESCE(SUM(LENGTH(n.content)),0)
                    FROM courses c LEFT JOIN notes n ON n.course_id=c.id
                    LEFT JOIN tasks t ON t.course_id=c.id LEFT JOIN resources r ON r.course_id=c.id
                    WHERE c.id=? GROUP BY c.id,c.code,c.name""", (payload,))
                self.result.emit(operation, cur.fetchone())
            elif operation == "attachments":
                cur.execute("""SELECT id,file_name,file_path,mime_type,file_size,created_at
                    FROM attachments WHERE note_id=? ORDER BY created_at DESC""", (payload,))
                self.result.emit(operation, cur.fetchall())
            elif operation == "save_attachment":
                cur.execute("""INSERT INTO attachments(note_id,file_name,file_path,mime_type,file_size,created_at)
                    VALUES(?,?,?,?,?,?)""", (*payload, now()))
                self.conn.commit()
                self.result.emit(operation, cur.lastrowid)
            elif operation == "delete_attachment":
                cur.execute("DELETE FROM attachments WHERE id=?", (payload,))
                self.conn.commit()
                self.result.emit(operation, None)
            elif operation == "save_note":
                note_id, course_id, title, category, content, tags, mode = payload
                timestamp = now()
                if note_id:
                    cur.execute("SELECT title,content FROM notes WHERE id=?", (note_id,))
                    previous = cur.fetchone()
                    if previous:
                        cur.execute("INSERT INTO note_versions(note_id,title,content,saved_at) VALUES(?,?,?,?)",
                                    (note_id, previous[0], previous[1], timestamp))
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
            elif operation == "duplicate_note":
                cur.execute("SELECT course_id,title,category,content,tags,editor_mode FROM notes WHERE id=?", (payload,))
                source = cur.fetchone()
                if not source:
                    raise ValueError("Note not found")
                timestamp = now()
                cur.execute("""INSERT INTO notes(course_id,title,category,content,tags,editor_mode,updated_at,created_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                            (source[0], f"{source[1]} (Copy)", source[2], source[3], source[4], source[5], timestamp, timestamp))
                self.conn.commit()
                self.result.emit(operation, cur.lastrowid)
            elif operation == "set_note_state":
                field = "is_favorite" if payload[0] == "favorite" else "is_archived"
                cur.execute(f"UPDATE notes SET {field}=? WHERE id=?", (int(payload[1]), payload[2]))
                self.conn.commit()
                self.result.emit(operation, None)
            elif operation == "tasks":
                cur.execute("""SELECT t.id,t.title,t.description,t.due_date,t.priority,t.status,coalesce(c.code,'')
                    FROM tasks t LEFT JOIN courses c ON c.id=t.course_id
                    ORDER BY CASE WHEN t.status='Open' THEN 0 ELSE 1 END, t.due_date""")
                self.result.emit(operation, cur.fetchall())
            elif operation == "save_task":
                task_id, course_id, title, description, due_date, priority, status = payload
                if task_id:
                    cur.execute("UPDATE tasks SET course_id=?,title=?,description=?,due_date=?,priority=?,status=? WHERE id=?",
                                (course_id,title,description,due_date,priority,status,task_id))
                else:
                    cur.execute("INSERT INTO tasks(course_id,title,description,due_date,priority,status,created_at) VALUES(?,?,?,?,?,?,?)",
                                (course_id,title,description,due_date,priority,status,now()))
                self.conn.commit(); self.result.emit(operation, None)
            elif operation == "toggle_task":
                cur.execute("UPDATE tasks SET status=?,completed_at=? WHERE id=?",
                            ("Completed" if payload[1] else "Open", now() if payload[1] else None, payload[0]))
                self.conn.commit(); self.result.emit(operation, None)
            elif operation == "resources":
                cur.execute("""SELECT r.id,r.title,r.url,r.description,r.tags,coalesce(c.code,'')
                    FROM resources r LEFT JOIN courses c ON c.id=r.course_id ORDER BY r.created_at DESC""")
                self.result.emit(operation, cur.fetchall())
            elif operation == "save_resource":
                resource_id, course_id, title, url, description, tags = payload
                if resource_id:
                    cur.execute("UPDATE resources SET course_id=?,title=?,url=?,description=?,tags=? WHERE id=?",
                                (course_id,title,url,description,tags,resource_id))
                else:
                    cur.execute("INSERT INTO resources(course_id,title,url,description,tags,created_at) VALUES(?,?,?,?,?,?)",
                                (course_id,title,url,description,tags,now()))
                self.conn.commit(); self.result.emit(operation, None)
            elif operation == "versions":
                cur.execute("SELECT id,title,content,saved_at FROM note_versions WHERE note_id=? ORDER BY saved_at DESC", (payload,))
                self.result.emit(operation, cur.fetchall())
            elif operation == "export_data":
                tables = {}
                for table in ("courses", "notes", "tasks", "resources", "profile", "chat_messages"):
                    cur.execute(f"SELECT * FROM {table}")
                    tables[table] = {"columns": [item[0] for item in cur.description], "rows": cur.fetchall()}
                with open(payload, "w", encoding="utf-8") as handle:
                    json.dump(tables, handle, indent=2, default=str)
                self.result.emit(operation, payload)
            elif operation == "import_data":
                with open(payload, "r", encoding="utf-8") as handle:
                    exported = json.load(handle)
                for table in ("courses", "notes", "tasks", "resources", "chat_messages"):
                    spec = exported.get(table)
                    if not spec:
                        continue
                    columns = [column for column in spec["columns"] if column != "id"]
                    placeholders = ",".join("?" for _ in columns)
                    for row in spec["rows"]:
                        values = [row[spec["columns"].index(column)] for column in columns]
                        cur.execute(f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
                profile = exported.get("profile")
                if profile:
                    columns = profile["columns"]
                    values = profile["rows"][0]
                    cur.execute(
                        f"INSERT OR REPLACE INTO profile ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                        values,
                    )
                self.conn.commit()
                self.result.emit(operation, payload)
            elif operation == "backup":
                self.conn.commit()
                shutil.copy2(DB_FILE, payload)
                self.result.emit(operation, payload)
            elif operation == "delete_resource":
                cur.execute("DELETE FROM resources WHERE id=?", (payload,)); self.conn.commit(); self.result.emit(operation, None)
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
                activity = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM tasks WHERE status='Open'")
                open_tasks = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM tasks WHERE status='Completed'")
                completed_tasks = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM resources")
                resources = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM notes WHERE COALESCE(is_favorite,0)=1")
                favorites = cur.fetchone()[0]
                self.result.emit(operation, (totals, categories, activity, open_tasks,
                                             completed_tasks, resources, favorites))
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
