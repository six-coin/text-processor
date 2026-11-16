"""配置读写：默认值、未知键、损坏、原子写。"""

from __future__ import annotations

import json

import pytest

from app import settings
from app.errors import ConfigError
from app.system import theme


def test_defaults_written_on_first_load(tmp_path):
    path = tmp_path / "app.json"
    data = settings.Settings(path).load()
    assert path.exists()
    assert data["theme"] in theme.THEMES
    assert data["wrap"] is True
    assert data["recent"] == {}


def test_unknown_keys_survive(tmp_path):
    path = tmp_path / "app.json"
    path.write_text(json.dumps({"theme": "dark", "future": {"a": 1}}), encoding="utf-8")
    store = settings.Settings(path)
    store.load()
    store.set("wrap", False)
    store.save()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["future"] == {"a": 1}
    assert raw["theme"] == "dark"
    assert raw["wrap"] is False


def test_broken_json_raises(tmp_path):
    path = tmp_path / "app.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        settings.Settings(path).load()


def test_no_temp_file_left(tmp_path):
    path = tmp_path / "app.json"
    store = settings.Settings(path)
    store.load()
    store.save()
    assert [item.name for item in tmp_path.iterdir()] == ["app.json"]


def test_theme_resolve():
    assert theme.resolve("dark") == "dark"
    assert theme.resolve("light") == "light"
    assert theme.resolve("nonsense") == "light"
    assert theme.resolve("system") in theme.THEMES


def test_recent_is_capped(tmp_path):
    store = settings.Settings(tmp_path / "app.json")
    store.load()
    for index in range(60):
        store.remember(f"p{index}", {"x": index}, False)
    assert len(store.recent_for("p59")["params"]) == 1
    assert store.recent_for("p0") == {}


def test_recent_roundtrip(tmp_path):
    path = tmp_path / "app.json"
    store = settings.Settings(path)
    store.load()
    store.remember("trim", {"chars": " "}, True)
    store.save()
    again = settings.Settings(path)
    again.load()
    assert again.recent_for("trim") == {"params": {"chars": " "}, "compare": True}


def test_font_size_clamped():
    assert settings.coerce_font_size(16) == 16
    assert settings.coerce_font_size("18") == 18
    assert settings.coerce_font_size(200) == settings.DEFAULT_FONT_SIZE
    assert settings.coerce_font_size("abc") == settings.DEFAULT_FONT_SIZE
    assert settings.coerce_font_size(None) == settings.DEFAULT_FONT_SIZE


def test_font_size_roundtrip(tmp_path):
    path = tmp_path / "app.json"
    store = settings.Settings(path)
    store.load()
    store.set("font_size", 18)
    store.save()
    again = settings.Settings(path)
    assert again.load()["font_size"] == 18
