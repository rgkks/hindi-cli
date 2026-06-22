from utils.platform import get_app_dir, get_cache_dir


class TestPaths:
    def test_app_dir_ends_with_hindi_cli(self):
        path = get_app_dir()
        assert path.name == "hindi-cli"

    def test_cache_dir_ends_with_hindi_cli(self):
        path = get_cache_dir()
        assert path.name == "hindi-cli"
