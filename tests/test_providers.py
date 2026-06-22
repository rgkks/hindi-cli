from providers.base import Provider, ChannelProvider, ProviderRegistry


class _TestProvider(Provider):
    name = "test"
    category = "test_category"

    def search(self, query: str, **kwargs):
        return [{"title": f"result for {query}"}]

    def resolve(self, url: str, **kwargs):
        return {"title": "resolved", "url": url}


class _TestChannelProvider(ChannelProvider):
    name = "test_channel"
    category = "test_channel_category"
    channel_id = "UC_test"
    enabled = True

    def search(self, query: str, **kwargs):
        return []

    def resolve(self, url: str, **kwargs):
        return {}

    def get_feed(self, limit: int = 10):
        return []


class _TestDisabledChannel(ChannelProvider):
    name = "disabled_channel"
    category = "test_channel_category"
    channel_id = "UC_disabled"
    enabled = False

    def search(self, query: str, **kwargs):
        return []

    def resolve(self, url: str, **kwargs):
        return {}

    def get_feed(self, limit: int = 10):
        return []


class TestProvider:
    def test_base_attributes(self):
        assert _TestProvider.name == "test"
        assert _TestProvider.category == "test_category"

    def test_search_returns_results(self):
        p = _TestProvider()
        results = p.search("hello")
        assert len(results) == 1
        assert results[0]["title"] == "result for hello"

    def test_resolve_returns_dict(self):
        p = _TestProvider()
        result = p.resolve("https://example.com/video")
        assert result["title"] == "resolved"
        assert result["url"] == "https://example.com/video"


class TestChannelProvider:
    def test_channel_attributes(self):
        p = _TestChannelProvider()
        assert p.channel_id == "UC_test"
        assert p.enabled is True

    def test_get_feed(self):
        p = _TestChannelProvider()
        assert p.get_feed() == []


class TestProviderRegistry:
    def setup_method(self):
        ProviderRegistry._providers.clear()

    def test_register(self):
        ProviderRegistry.register(_TestProvider())
        assert "test" in ProviderRegistry._providers

    def test_get(self):
        ProviderRegistry.register(_TestProvider())
        p = ProviderRegistry.get("test")
        assert p is not None
        assert p.name == "test"

    def test_get_nonexistent(self):
        assert ProviderRegistry.get("nonexistent") is None

    def test_get_by_category(self):
        ProviderRegistry.register(_TestProvider())
        cat = ProviderRegistry.get_by_category("test_category")
        assert "test" in cat

    def test_get_by_category_empty(self):
        assert ProviderRegistry.get_by_category("nonexistent") == {}

    def test_get_channels_returns_only_enabled(self):
        ProviderRegistry.register(_TestChannelProvider())
        ProviderRegistry.register(_TestDisabledChannel())
        channels = ProviderRegistry.get_channels("test_channel_category")
        assert "test_channel" in channels
        assert "disabled_channel" not in channels

    def test_get_channels_empty_for_unknown_category(self):
        assert ProviderRegistry.get_channels("ghost") == {}
