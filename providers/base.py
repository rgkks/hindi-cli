from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Provider(ABC):
    name: str = ""
    description: str = ""
    category: str = ""
    enabled: bool = True

    @abstractmethod
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        pass

    def latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.search("", limit=limit)


class ChannelProvider(Provider):
    channel_url: str = ""
    channel_name: str = ""
    languages: List[str] = []


class ProviderRegistry:
    _providers: Dict[str, Provider] = {}

    @classmethod
    def register(cls, provider: Provider):
        if provider.name:
            cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> Optional[Provider]:
        return cls._providers.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, Provider]:
        return cls._providers

    @classmethod
    def get_by_category(cls, category: str) -> Dict[str, Provider]:
        return {n: p for n, p in cls._providers.items()
                if getattr(p, "category", "") == category}

    @classmethod
    def get_channels(cls, category: str) -> Dict[str, ChannelProvider]:
        return {n: p for n, p in cls._providers.items()
                if isinstance(p, ChannelProvider) and p.category == category}
