import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from core.config import Config
from utils.logger import log
from utils.platform import get_app_dir


DB_PATH = get_app_dir() / "history.db"


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._history_ops = 0
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-8000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS watch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_type TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                provider TEXT DEFAULT '',
                episode INTEGER DEFAULT 0,
                position REAL DEFAULT 0.0,
                duration REAL DEFAULT 0.0,
                watched_at REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS liked_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                media_type TEXT NOT NULL,
                added_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS anime_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id TEXT NOT NULL,
                title TEXT NOT NULL,
                episode INTEGER NOT NULL,
                position REAL DEFAULT 0.0,
                duration REAL DEFAULT 0.0,
                provider TEXT DEFAULT '',
                url TEXT DEFAULT '',
                updated_at REAL NOT NULL,
                UNIQUE(anime_id, episode)
            );
            CREATE TABLE IF NOT EXISTS movie_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                position REAL DEFAULT 0.0,
                duration REAL DEFAULT 0.0,
                provider TEXT DEFAULT '',
                url TEXT DEFAULT '',
                language TEXT DEFAULT '',
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_history_type ON watch_history(media_type);
            CREATE INDEX IF NOT EXISTS idx_history_time ON watch_history(watched_at DESC);
            CREATE INDEX IF NOT EXISTS idx_anime_progress ON anime_progress(anime_id);
            CREATE INDEX IF NOT EXISTS idx_liked_type ON liked_videos(media_type);
        """)
        self.conn.commit()

    def add_to_history(self, media_type: str, title: str, url: str,
                       provider: str = "", episode: int = 0,
                       position: float = 0.0, duration: float = 0.0,
                       metadata: Optional[dict] = None):
        try:
            self.conn.execute(
                """INSERT INTO watch_history (media_type, title, url, provider,
                   episode, position, duration, watched_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (media_type, title, url, provider, episode, position, duration,
                 time.time(), json.dumps(metadata or {}))
            )
            self._history_ops += 1
            if self._history_ops >= 20:
                self._history_ops = 0
                limit = Config().get("behavior", "history_size", default=500)
                if not isinstance(limit, int) or limit < 1:
                    limit = 500
                self.conn.execute(
                    "DELETE FROM watch_history WHERE id NOT IN ("
                    "SELECT id FROM watch_history ORDER BY watched_at DESC LIMIT ?)",
                    (limit,)
                )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error(f"Database add_to_history error: {e}")

    def get_history(self, media_type: Optional[str] = None, limit: int = 50):
        if media_type:
            cur = self.conn.execute(
                "SELECT * FROM watch_history WHERE media_type = ? ORDER BY watched_at DESC LIMIT ?",
                (media_type, limit)
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM watch_history ORDER BY watched_at DESC LIMIT ?",
                (limit,)
            )
        return [dict(r) for r in cur.fetchall()]

    def _exec(self, sql: str, params=()):
        try:
            self.conn.execute(sql, params)
            self.conn.commit()
        except sqlite3.Error as e:
            log.error(f"Database error: {e}")

    def add_liked(self, url: str, title: str, media_type: str):
        self._exec(
            "INSERT OR IGNORE INTO liked_videos (url, title, media_type, added_at) VALUES (?, ?, ?, ?)",
            (url, title, media_type, time.time())
        )

    def get_liked(self, media_type: Optional[str] = None):
        if media_type:
            cur = self.conn.execute(
                "SELECT * FROM liked_videos WHERE media_type = ? ORDER BY added_at DESC",
                (media_type,)
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM liked_videos ORDER BY added_at DESC"
            )
        return [dict(r) for r in cur.fetchall()]

    def update_anime_progress(self, anime_id: str, title: str, episode: int,
                                position: float, duration: float,
                                provider: str = "", url: str = ""):
        self._exec(
            """INSERT OR REPLACE INTO anime_progress
               (anime_id, title, episode, position, duration, provider, url, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (anime_id, title, episode, position, duration, provider, url, time.time())
        )

    def get_anime_progress(self, anime_id: str):
        cur = self.conn.execute(
            "SELECT * FROM anime_progress WHERE anime_id = ? ORDER BY episode DESC LIMIT 1",
            (anime_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_all_anime_progress(self):
        cur = self.conn.execute(
            """SELECT * FROM anime_progress WHERE id IN
               (SELECT MAX(id) FROM anime_progress GROUP BY anime_id)
               ORDER BY updated_at DESC"""
        )
        return [dict(r) for r in cur.fetchall()]

    def update_movie_progress(self, movie_id: str, title: str,
                                position: float, duration: float,
                                provider: str = "", url: str = "",
                                language: str = ""):
        self._exec(
            """INSERT OR REPLACE INTO movie_progress
               (movie_id, title, position, duration, provider, url, language, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (movie_id, title, position, duration, provider, url, language, time.time())
        )

    def get_movie_progress(self, movie_id: str):
        cur = self.conn.execute(
            "SELECT * FROM movie_progress WHERE movie_id = ?",
            (movie_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_all_movie_progress(self):
        cur = self.conn.execute(
            "SELECT * FROM movie_progress ORDER BY updated_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]

    def get_stats(self) -> dict:
        cur = self.conn.execute("SELECT COUNT(*) as total FROM watch_history")
        total = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM watch_history WHERE media_type='youtube'")
        videos = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM watch_history WHERE media_type='anime'")
        anime = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM watch_history WHERE media_type='movie'")
        movies = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM liked_videos")
        liked = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM anime_progress")
        anime_progress = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) as c FROM movie_progress")
        movies_progress = cur.fetchone()[0]
        return {
            "total_watched": total,
            "videos": videos,
            "anime": anime,
            "movies": movies,
            "liked": liked,
            "anime_in_progress": anime_progress,
            "movies_in_progress": movies_progress,
        }

    def clear_history(self, media_type: Optional[str] = None):
        try:
            if media_type:
                self.conn.execute("DELETE FROM watch_history WHERE media_type = ?", (media_type,))
                if media_type == "anime":
                    self.conn.execute("DELETE FROM anime_progress")
                elif media_type == "movie":
                    self.conn.execute("DELETE FROM movie_progress")
            else:
                self.conn.execute("DELETE FROM watch_history")
                self.conn.execute("DELETE FROM anime_progress")
                self.conn.execute("DELETE FROM movie_progress")
            self.conn.commit()
        except sqlite3.Error as e:
            log.error(f"Database clear_history error: {e}")

    def remove_history_item(self, item_id: int):
        self.conn.execute("DELETE FROM watch_history WHERE id = ?", (item_id,))
        self.conn.commit()

    def update_history_position(self, url: str, position: float):
        try:
            self.conn.execute(
                "UPDATE watch_history SET position = ? WHERE id = (SELECT MAX(id) FROM watch_history WHERE url = ?)",
                (position, url)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error(f"Database update_history_position error: {e}")

    def update_playback_position(self, media_type: str, item_id: str, title: str,
                                   position: float, duration: float,
                                   provider: str = "", url: str = ""):
        try:
            if media_type == "anime":
                self.conn.execute(
                    """UPDATE anime_progress SET position = ?, duration = ?, updated_at = ?
                       WHERE anime_id = ?""",
                    (position, duration, time.time(), item_id)
                )
            elif media_type == "movie":
                self.conn.execute(
                    """UPDATE movie_progress SET position = ?, duration = ?, updated_at = ?
                       WHERE movie_id = ?""",
                    (position, duration, time.time(), item_id)
                )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error(f"Database update_playback_position error: {e}")

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error as e:
            log.error(f"Database close error: {e}")


db = Database()
