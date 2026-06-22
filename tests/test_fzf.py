from core.fzf import FZF


class TestFZF:
    def test_menu_empty_items(self):
        assert FZF.menu([], prompt="test") is None

    def test_confirm_empty(self):
        assert FZF.confirm("") is False

    def test_confirm_default(self):
        """Should return False by default (no selection in non-interactive mode)."""
        assert FZF.confirm() is False
