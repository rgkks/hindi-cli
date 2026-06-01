import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


class PluginMeta(type):
    plugins: Dict[str, Type["BasePlugin"]] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BasePlugin" and hasattr(cls, "name"):
            PluginMeta.plugins[cls.name] = cls
        return cls


class BasePlugin(metaclass=PluginMeta):
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""

    def __init__(self):
        self.enabled = True

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def on_menu_open(self, menu_name: str) -> Optional[List[str]]:
        return None

    def on_item_select(self, item: str) -> Optional[Any]:
        return None

    def on_playback_start(self, url: str, **kwargs):
        pass

    def on_playback_end(self, url: str, **kwargs):
        pass


class PluginManager:
    def __init__(self, plugins_dir: str):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.loaded: Dict[str, BasePlugin] = {}
        self._load_plugins()

    def _load_plugins(self):
        if not self.plugins_dir.exists():
            return
        for f in self.plugins_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(f.stem, str(f))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
            except Exception as e:
                print(f"Failed to load plugin {f.name}: {e}")

        for name, cls in PluginMeta.plugins.items():
            if name not in self.loaded:
                try:
                    instance = cls()
                    instance.on_load()
                    self.loaded[name] = instance
                except Exception as e:
                    print(f"Failed to init plugin {name}: {e}")

    def get_plugins(self) -> Dict[str, BasePlugin]:
        return self.loaded

    def trigger(self, event: str, **kwargs) -> List[Any]:
        results = []
        for name, plugin in self.loaded.items():
            if not plugin.enabled:
                continue
            handler = getattr(plugin, event, None)
            if handler:
                try:
                    result = handler(**kwargs)
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    print(f"Plugin {name} error in {event}: {e}")
        return results
