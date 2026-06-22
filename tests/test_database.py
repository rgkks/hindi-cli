import tempfile
from pathlib import Path
from unittest.mock import patch

import core.database as db_module


class TestDatabase:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        target = self.tmp / "test.db"
        db_module.Database._instance = None
        with patch.object(db_module, "DB_PATH", target):
            target.parent.mkdir(parents=True, exist_ok=True)
            self.db = db_module.Database()

    def teardown_method(self):
        try:
            self.db.close()
        except Exception:
            pass

    def test_add_and_get_history(self):
        self.db.add_to_history("video", "Test Video", "https://example.com/v1",
                               provider="youtube", duration=120.0)
        results = self.db.get_history(limit=10)
        assert len(results) == 1
        assert results[0]["title"] == "Test Video"
        assert results[0]["url"] == "https://example.com/v1"

    def test_history_pagination(self):
        for i in range(5):
            self.db.add_to_history("video", f"Video {i}", f"https://example.com/v{i}")
        assert len(self.db.get_history(limit=10)) == 5
        assert len(self.db.get_history(limit=2)) == 2

    def test_get_history_empty(self):
        assert self.db.get_history(limit=10) == []

    def test_get_history_by_type(self):
        self.db.add_to_history("video", "V1", "https://example.com/v1")
        self.db.add_to_history("anime", "A1", "https://example.com/a1")
        assert len(self.db.get_history("video", limit=10)) == 1
        assert len(self.db.get_history("anime", limit=10)) == 1
        assert len(self.db.get_history("movie", limit=10)) == 0

    def test_add_liked(self):
        self.db.add_liked("https://example.com/v1", "Test Video", "video")
        liked = self.db.get_liked()
        assert len(liked) == 1
        assert liked[0]["title"] == "Test Video"

    def test_get_liked_by_type(self):
        self.db.add_liked("https://example.com/v1", "Video A", "video")
        self.db.add_liked("https://example.com/a1", "Anime A", "anime")
        assert len(self.db.get_liked("video")) == 1
        assert len(self.db.get_liked("anime")) == 1

    def test_add_liked_ignore_duplicate(self):
        self.db.add_liked("https://example.com/v1", "Video A", "video")
        self.db.add_liked("https://example.com/v1", "Video A", "video")
        assert len(self.db.get_liked()) == 1

    def test_get_liked_empty(self):
        assert self.db.get_liked() == []

    def test_anime_progress(self):
        self.db.update_anime_progress("a1", "Anime 1", 1, 300.0, 1200.0)
        progress = self.db.get_anime_progress("a1")
        assert progress["title"] == "Anime 1"
        assert progress["episode"] == 1

    def test_get_anime_progress_nonexistent(self):
        assert self.db.get_anime_progress("nonexistent") is None

    def test_movie_progress(self):
        self.db.update_movie_progress("m1", "Movie 1", 600.0, 3600.0)
        progress = self.db.get_movie_progress("m1")
        assert progress["title"] == "Movie 1"

    def test_get_movie_progress_nonexistent(self):
        assert self.db.get_movie_progress("nonexistent") is None

    def test_get_stats(self):
        self.db.add_to_history("youtube", "V1", "https://example.com/v1")
        self.db.add_to_history("anime", "A1", "https://example.com/a1")
        self.db.add_to_history("movie", "M1", "https://example.com/m1")
        stats = self.db.get_stats()
        assert stats["total_watched"] == 3
        assert stats["videos"] == 1
        assert stats["anime"] == 1
        assert stats["movies"] == 1

    def test_get_stats_empty(self):
        stats = self.db.get_stats()
        assert stats["total_watched"] == 0

    def test_clear_history_all(self):
        self.db.add_to_history("video", "V1", "https://example.com/v1")
        self.db.add_to_history("anime", "A1", "https://example.com/a1")
        self.db.clear_history()
        assert len(self.db.get_history(limit=10)) == 0

    def test_clear_history_by_type(self):
        self.db.add_to_history("video", "V1", "https://example.com/v1")
        self.db.add_to_history("anime", "A1", "https://example.com/a1")
        self.db.clear_history("anime")
        history = self.db.get_history(limit=10)
        assert len(history) == 1
        assert history[0]["media_type"] == "video"

    def test_remove_history_item(self):
        self.db.add_to_history("video", "V1", "https://example.com/v1")
        self.db.add_to_history("video", "V2", "https://example.com/v2")
        history = self.db.get_history(limit=10)
        target_id = history[0]["id"]
        self.db.remove_history_item(target_id)
        remaining = self.db.get_history(limit=10)
        assert len(remaining) == 1
        assert remaining[0]["id"] != target_id

    def test_close_safe(self):
        self.db.close()
        self.db.close()

    def test_error_resilience(self):
        self.db.conn.close()
        self.db.add_to_history("video", "Fail", "https://x.com")
        self.db.clear_history()
        self.db.close()
