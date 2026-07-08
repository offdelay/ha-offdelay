"""Tests for import asset copying in ``custom_components.offdelay.imports``."""

from __future__ import annotations

from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from custom_components.offdelay.const import DOMAIN
import custom_components.offdelay.imports as imports_module


async def _executor_job(func, *args):
    """Run a sync function in executor (mock — runs inline)."""
    return func(*args)


class _MockConfig:
    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    def path(self, *parts: str) -> str:
        return str(self._base_path.joinpath(*parts))


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_source_imports(tmp_path: Path, monkeypatch) -> Path:
    source_imports = tmp_path / "source" / "imports"
    source_file = source_imports.parent / "imports.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(imports_module, "__file__", str(source_file))
    return source_imports


class _MockLovelaceData:
    def __init__(self, resources) -> None:
        self.resources = resources


def test_iter_community_resource_urls_selects_one_main_file_per_folder(
    tmp_path: Path,
) -> None:
    """Community module selection prefers the primary JavaScript file."""
    community_dir = tmp_path / "community"
    _write_file(community_dir / "Bubble-Card" / "bubble-card.js", "main")
    _write_file(community_dir / "Bubble-Card" / "bubble-pop-up-fix.js", "helper")
    _write_file(community_dir / "kiosk-mode" / "kiosk-mode.js", "main")
    _write_file(community_dir / "kiosk-mode" / "kiosk-mode-es5.js", "legacy")

    assert imports_module._iter_community_resource_urls(community_dir) == {
        "Bubble-Card": "/local/community/Bubble-Card/bubble-card.js",
        "kiosk-mode": "/local/community/kiosk-mode/kiosk-mode.js",
    }


def test_copy_import_assets_to_ha_config(tmp_path: Path, monkeypatch) -> None:
    """Copies import assets and folder-based imports into HA config locations."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)

    # Prepare import files structure
    (source_imports / "blueprints" / "automation" / DOMAIN).mkdir(parents=True)
    (source_imports / "blueprints" / "script" / DOMAIN).mkdir(parents=True)
    (
        source_imports / "blueprints" / "automation" / DOMAIN / "automation.yaml"
    ).write_text("description: Test")
    _write_file(
        source_imports / "blueprints" / "script" / DOMAIN / "script.yaml",
        "script: true\n",
    )
    _write_file(
        source_imports / "custom_components" / "demo_integration" / "manifest.json",
        '{"domain": "demo_integration"}',
    )
    _write_file(
        source_imports / "themes" / "demo_theme" / "theme.yaml",
        "demo_theme:\n  primary-color: '#000000'\n",
    )
    _write_file(
        source_imports / "community" / "demo-card" / "demo-card.js",
        "console.log('demo');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(config=_MockConfig(ha_config_path))

    imports_module.copy_imports(hass, DOMAIN)

    assert (
        ha_config_path / "blueprints" / "automation" / DOMAIN / "automation.yaml"
    ).is_file()
    assert (ha_config_path / "blueprints" / "script" / DOMAIN / "script.yaml").is_file()
    assert (
        ha_config_path / "custom_components" / "demo_integration" / "manifest.json"
    ).is_file()
    assert (ha_config_path / "themes" / "demo_theme" / "theme.yaml").is_file()
    assert (
        ha_config_path / "www" / "community" / "demo-card" / "demo-card.js"
    ).is_file()


def test_copy_import_folders_replace_existing_destination(
    tmp_path: Path, monkeypatch
) -> None:
    """Existing destination folders are replaced for folder-based import types."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "custom_components" / "demo" / "new_file.txt",
        "new-data",
    )
    _write_file(
        source_imports / "themes" / "demo_theme" / "new_theme.yaml", "new-theme"
    )
    _write_file(source_imports / "community" / "demo_card" / "new_card.js", "new-card")

    ha_config_path = tmp_path / "ha"
    _write_file(
        ha_config_path / "custom_components" / "demo" / "old_file.txt",
        "old-data",
    )
    _write_file(
        ha_config_path / "themes" / "demo_theme" / "old_theme.yaml",
        "old-theme",
    )
    _write_file(
        ha_config_path / "www" / "community" / "demo_card" / "old_card.js",
        "old-card",
    )

    hass = SimpleNamespace(config=_MockConfig(ha_config_path))

    imports_module.copy_imports(hass, DOMAIN)

    assert not (ha_config_path / "custom_components" / "demo" / "old_file.txt").exists()
    assert not (ha_config_path / "themes" / "demo_theme" / "old_theme.yaml").exists()
    assert not (
        ha_config_path / "www" / "community" / "demo_card" / "old_card.js"
    ).exists()

    assert (ha_config_path / "custom_components" / "demo" / "new_file.txt").is_file()
    assert (ha_config_path / "themes" / "demo_theme" / "new_theme.yaml").is_file()
    assert (
        ha_config_path / "www" / "community" / "demo_card" / "new_card.js"
    ).is_file()


def test_copy_imports_skips_unchanged_assets(tmp_path: Path, monkeypatch) -> None:
    """Unchanged import assets are left untouched on repeated setup."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "blueprints" / "automation" / DOMAIN / "automation.yaml",
        "description: same\n",
    )
    _write_file(
        source_imports / "custom_components" / "demo" / "manifest.json",
        '{"domain": "demo"}\n',
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(config=_MockConfig(ha_config_path))

    imports_module.copy_imports(hass, DOMAIN)

    destination_blueprint = (
        ha_config_path / "blueprints" / "automation" / DOMAIN / "automation.yaml"
    )
    destination_component = (
        ha_config_path / "custom_components" / "demo" / "manifest.json"
    )
    blueprint_mtime = destination_blueprint.stat().st_mtime_ns
    component_mtime = destination_component.stat().st_mtime_ns

    imports_module.copy_imports(hass, DOMAIN)

    assert destination_blueprint.stat().st_mtime_ns == blueprint_mtime
    assert destination_component.stat().st_mtime_ns == component_mtime


def test_copy_imports_replaces_changed_folder_assets(
    tmp_path: Path, monkeypatch
) -> None:
    """Changed folder imports replace the destination tree on later setup runs."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    source_component_dir = source_imports / "custom_components" / "demo"
    _write_file(source_component_dir / "manifest.json", '{"domain": "demo"}\n')

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(config=_MockConfig(ha_config_path))

    imports_module.copy_imports(hass, DOMAIN)

    destination_component_dir = ha_config_path / "custom_components" / "demo"
    original_tree = destination_component_dir / "extra.txt"
    _write_file(original_tree, "stale\n")

    shutil.rmtree(source_component_dir)
    _write_file(
        source_component_dir / "manifest.json", '{"domain": "demo", "version": 2}\n'
    )

    imports_module.copy_imports(hass, DOMAIN)

    assert not original_tree.exists()
    assert (destination_component_dir / "manifest.json").read_text(
        encoding="utf-8"
    ) == ('{"domain": "demo", "version": 2}\n')


async def test_async_setup_imports_registers_missing_community_resources(
    tmp_path: Path, monkeypatch
) -> None:
    """Missing community JavaScript modules are added to Lovelace resources."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "community" / "demo-card" / "demo-card.js",
        "console.log('demo');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(
        config=_MockConfig(ha_config_path),
        data={},
        async_add_executor_job=_executor_job,
    )

    resources = object.__new__(ResourceStorageCollection)
    resources.loaded = True
    resources.async_items = lambda: []
    resources.async_create_item = AsyncMock()
    resources.async_load = AsyncMock()
    hass.data[LOVELACE_DATA] = _MockLovelaceData(resources)

    await imports_module.async_setup_imports(hass, DOMAIN)

    resources.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": "/local/community/demo-card/demo-card.js"}
    )
    resources.async_load.assert_not_called()


async def test_async_setup_imports_skips_existing_community_resources(
    tmp_path: Path, monkeypatch
) -> None:
    """Existing community Lovelace resources are not duplicated."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "community" / "demo-card" / "demo-card.js",
        "console.log('demo');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(
        config=_MockConfig(ha_config_path),
        data={},
        async_add_executor_job=_executor_job,
    )

    resources = object.__new__(ResourceStorageCollection)
    resources.loaded = True
    resources.async_items = lambda: [
        {"id": "1", "type": "module", "url": "/local/community/demo-card/demo-card.js"}
    ]
    resources.async_create_item = AsyncMock()
    resources.async_load = AsyncMock()
    hass.data[LOVELACE_DATA] = _MockLovelaceData(resources)

    await imports_module.async_setup_imports(hass, DOMAIN)

    resources.async_create_item.assert_not_awaited()


async def test_async_setup_imports_updates_main_resource_and_removes_extras(
    tmp_path: Path, monkeypatch
) -> None:
    """Community resources keep only one main JavaScript resource per folder."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "community" / "kiosk-mode" / "kiosk-mode.js",
        "console.log('main');\n",
    )
    _write_file(
        source_imports / "community" / "kiosk-mode" / "kiosk-mode-es5.js",
        "console.log('legacy');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(
        config=_MockConfig(ha_config_path),
        data={},
        async_add_executor_job=_executor_job,
    )

    resources = object.__new__(ResourceStorageCollection)
    resources.loaded = True
    resources.async_items = lambda: [
        {
            "id": "1",
            "type": "module",
            "url": "/local/community/kiosk-mode/kiosk-mode-es5.js",
        },
        {
            "id": "2",
            "type": "module",
            "url": "/local/community/kiosk-mode/kiosk-mode.js",
        },
    ]
    resources.async_create_item = AsyncMock()
    resources.async_update_item = AsyncMock()
    resources.async_delete_item = AsyncMock()
    resources.async_load = AsyncMock()
    hass.data[LOVELACE_DATA] = _MockLovelaceData(resources)

    await imports_module.async_setup_imports(hass, DOMAIN)

    resources.async_create_item.assert_not_awaited()
    resources.async_update_item.assert_not_awaited()
    resources.async_delete_item.assert_awaited_once_with("1")


async def test_async_setup_imports_replaces_wrong_existing_resource(
    tmp_path: Path, monkeypatch
) -> None:
    """A helper or legacy resource is updated to the selected main file."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "community" / "Bubble-Card" / "bubble-card.js",
        "console.log('main');\n",
    )
    _write_file(
        source_imports / "community" / "Bubble-Card" / "bubble-pop-up-fix.js",
        "console.log('helper');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(
        config=_MockConfig(ha_config_path),
        data={},
        async_add_executor_job=_executor_job,
    )

    resources = object.__new__(ResourceStorageCollection)
    resources.loaded = True
    resources.async_items = lambda: [
        {
            "id": "1",
            "type": "module",
            "url": "/local/community/Bubble-Card/bubble-pop-up-fix.js",
        }
    ]
    resources.async_create_item = AsyncMock()
    resources.async_update_item = AsyncMock()
    resources.async_delete_item = AsyncMock()
    resources.async_load = AsyncMock()
    hass.data[LOVELACE_DATA] = _MockLovelaceData(resources)

    await imports_module.async_setup_imports(hass, DOMAIN)

    resources.async_update_item.assert_awaited_once_with(
        "1", {"url": "/local/community/Bubble-Card/bubble-card.js"}
    )
    resources.async_delete_item.assert_not_awaited()


async def test_async_setup_imports_skips_lovelace_yaml_mode(
    tmp_path: Path, monkeypatch
) -> None:
    """YAML mode skips automatic community resource registration."""
    source_imports = _prepare_source_imports(tmp_path, monkeypatch)
    _write_file(
        source_imports / "community" / "demo-card" / "demo-card.js",
        "console.log('demo');\n",
    )

    ha_config_path = tmp_path / "ha"
    hass = SimpleNamespace(
        config=_MockConfig(ha_config_path),
        data={LOVELACE_DATA: _MockLovelaceData(SimpleNamespace())},
        async_add_executor_job=_executor_job,
    )

    await imports_module.async_setup_imports(hass, DOMAIN)
