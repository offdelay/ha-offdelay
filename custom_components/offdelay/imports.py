"""Copy integration import assets into Home Assistant config."""

from __future__ import annotations

import filecmp
from fnmatch import fnmatch
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant

from .const import LOGGER as _LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable


def _files_match(source_file: Path, destination_file: Path) -> bool:
    """Return whether two files have identical contents."""
    return destination_file.is_file() and filecmp.cmp(
        source_file, destination_file, shallow=False
    )


def _is_ignored(path: Path, ignore: Iterable[str] | None) -> bool:
    """Return whether a path name matches the configured ignore patterns."""
    return ignore is not None and any(fnmatch(path.name, pattern) for pattern in ignore)


def _directories_match(
    source_dir: Path,
    destination_dir: Path,
    ignore: Iterable[str] | None = None,
) -> bool:
    """Return whether two directories have identical contents."""
    if not destination_dir.is_dir():
        return False

    source_entries = {
        entry.name: entry
        for entry in source_dir.iterdir()
        if entry.name != "__pycache__" and not _is_ignored(entry, ignore)
    }
    destination_entries = {
        entry.name: entry
        for entry in destination_dir.iterdir()
        if entry.name != "__pycache__" and not _is_ignored(entry, ignore)
    }

    if source_entries.keys() != destination_entries.keys():
        return False

    for name, source_entry in source_entries.items():
        destination_entry = destination_entries[name]
        if source_entry.is_dir():
            if not destination_entry.is_dir() or not _directories_match(
                source_entry, destination_entry, ignore
            ):
                return False
            continue

        if not source_entry.is_file() or not _files_match(
            source_entry, destination_entry
        ):
            return False

    return True


def _resolve_import_files_source(integration_imports_dir: Path) -> Path | None:
    """Resolve the import file source directory under imports."""
    source = integration_imports_dir / "blueprints-folder"
    if source.is_dir():
        return source
    return None


def _normalize_community_module_name(name: str) -> str:
    """Normalize a community module name for filename matching."""
    return name.casefold().removeprefix("lovelace-")


def _score_community_javascript_file(module_dir: Path, javascript_file: Path) -> tuple:
    """Return a sort key preferring the main JavaScript resource file."""
    module_name = _normalize_community_module_name(module_dir.name)
    file_stem = _normalize_community_module_name(javascript_file.stem)
    suffix_penalties = ("-es5", "-fix", "-legacy", "-bundle", ".umd")

    return (
        file_stem != module_name,
        any(file_stem.endswith(suffix) for suffix in suffix_penalties),
        len(file_stem),
        file_stem,
    )


def _select_community_javascript_file(module_dir: Path) -> Path | None:
    """Select the single JavaScript file to register for a community module."""
    javascript_files = sorted(module_dir.glob("*.js"))
    if not javascript_files:
        return None

    return min(
        javascript_files,
        key=lambda javascript_file: _score_community_javascript_file(
            module_dir, javascript_file
        ),
    )


def _iter_community_resource_urls(community_dir: Path) -> dict[str, str]:
    """Return one Lovelace resource URL per community module folder."""
    resource_urls: dict[str, str] = {}

    if not community_dir.is_dir():
        return resource_urls

    for module_dir in sorted(community_dir.iterdir()):
        if not module_dir.is_dir() or module_dir.name == "__pycache__":
            continue

        if javascript_file := _select_community_javascript_file(module_dir):
            resource_urls[module_dir.name] = (
                f"/local/community/{module_dir.name}/{javascript_file.name}"
            )

    return resource_urls


async def _async_get_lovelace_resources(
    hass: HomeAssistant,
) -> ResourceStorageCollection | None:
    """Return Lovelace storage resources when available."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.info("Lovelace not loaded; skipping community resource registration.")
        return None

    resources = lovelace_data.resources
    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.info(
            "Lovelace YAML mode detected; skipping community resource registration."
        )
        return None

    if not resources.loaded:
        await resources.async_load()

    return resources


async def _async_register_community_resources(hass: HomeAssistant, domain: str) -> None:
    """Register copied community JavaScript modules in Lovelace resources."""
    resources = await _async_get_lovelace_resources(hass)
    if resources is None:
        return

    community_dir = Path(hass.config.path("www", "community"))
    resource_urls = await hass.async_add_executor_job(
        _iter_community_resource_urls, community_dir
    )
    if not resource_urls:
        return

    existing_entries_by_module: dict[str, list[dict]] = {}
    for entry in resources.async_items():
        if entry.get("res_type", entry.get("type")) != "module":
            continue

        entry_url = entry.get("url")
        if not isinstance(entry_url, str) or not entry_url.startswith(
            "/local/community/"
        ):
            continue

        module_name, _, _ = entry_url.removeprefix("/local/community/").partition("/")
        if not module_name:
            continue

        existing_entries_by_module.setdefault(module_name, []).append(entry)

    for module_name, resource_url in resource_urls.items():
        existing_entries = existing_entries_by_module.get(module_name, [])
        matching_entry = next(
            (entry for entry in existing_entries if entry.get("url") == resource_url),
            None,
        )

        if matching_entry is None:
            if existing_entries:
                primary_entry, *extra_entries = existing_entries
                await resources.async_update_item(
                    primary_entry["id"], {"url": resource_url}
                )
                _LOGGER.info(
                    "Updated Lovelace community resource for %s: %s",
                    domain,
                    resource_url,
                )
                matching_entry = primary_entry
            else:
                matching_entry = await resources.async_create_item(
                    {"res_type": "module", "url": resource_url}
                )
                _LOGGER.info(
                    "Registered Lovelace community resource for %s: %s",
                    domain,
                    resource_url,
                )
                extra_entries = []
        else:
            extra_entries = [
                entry
                for entry in existing_entries
                if entry["id"] != matching_entry["id"]
            ]

        for extra_entry in extra_entries:
            await resources.async_delete_item(extra_entry["id"])
            _LOGGER.info(
                "Removed extra Lovelace community resource for %s: %s",
                domain,
                extra_entry["url"],
            )


def _copy_import_files(
    import_files_source_dir: Path, hass: HomeAssistant, domain: str
) -> None:
    """Copy import YAML files to the Home Assistant blueprints folders."""
    ha_blueprints_dir = Path(hass.config.path("blueprints"))

    for import_type in ("automation", "script"):
        source_dir = import_files_source_dir / import_type / domain
        if not source_dir.is_dir():
            continue

        destination_dir = ha_blueprints_dir / import_type / domain

        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as err:
            _LOGGER.warning(
                "Cannot create import destination directory %s: %s",
                destination_dir,
                err,
            )
            continue

        for import_file in source_dir.glob("*.yaml"):
            destination_file = destination_dir / import_file.name
            if _files_match(import_file, destination_file):
                continue
            try:
                shutil.copy2(import_file, destination_file)
            except (PermissionError, OSError) as err:
                _LOGGER.warning("Cannot copy import file %s: %s", destination_file, err)
                continue
            _LOGGER.debug(
                "Copied import file: %s/%s/%s",
                import_type,
                domain,
                import_file.name,
            )


def _copy_import_folders(
    source_parent_dir: Path,
    destination_parent_dir: Path,
    import_type: str,
    ignore: Iterable[str] | None = None,
) -> None:
    """Copy child folders from source into destination, replacing existing folders."""
    if not source_parent_dir.is_dir():
        return

    try:
        destination_parent_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as err:
        _LOGGER.warning(
            "Cannot create %s destination directory %s: %s",
            import_type,
            destination_parent_dir,
            err,
        )
        return

    ignore_patterns = shutil.ignore_patterns(*ignore) if ignore else None

    for source_dir in source_parent_dir.iterdir():
        if not source_dir.is_dir() or source_dir.name == "__pycache__":
            continue

        destination_dir = destination_parent_dir / source_dir.name
        if _directories_match(source_dir, destination_dir, ignore):
            continue

        if destination_dir.exists():
            try:
                shutil.rmtree(destination_dir)
            except (PermissionError, OSError) as err:
                _LOGGER.warning(
                    "Cannot replace existing %s directory %s: %s",
                    import_type,
                    destination_dir,
                    err,
                )
                continue

        try:
            shutil.copytree(source_dir, destination_dir, ignore=ignore_patterns)
        except (PermissionError, OSError) as err:
            _LOGGER.warning(
                "Cannot copy %s directory %s to %s: %s",
                import_type,
                source_dir,
                destination_dir,
                err,
            )
            continue

        _LOGGER.debug(
            "Copied %s folder: %s -> %s",
            import_type,
            source_dir,
            destination_dir,
        )


def copy_imports(hass: HomeAssistant, domain: str) -> None:
    """Copy import assets into Home Assistant config."""
    integration_imports_dir = Path(__file__).parent / "imports"
    if not integration_imports_dir.is_dir():
        _LOGGER.debug("No imports folder found in integration directory.")
        return

    import_files_source_dir = _resolve_import_files_source(integration_imports_dir)
    if import_files_source_dir is None:
        _LOGGER.debug("No import file source folder found under imports.")
    else:
        _copy_import_files(import_files_source_dir, hass, domain)

    _copy_import_folders(
        integration_imports_dir / "custom_components",
        Path(hass.config.path("custom_components")),
        "custom_components",
        ignore=("__pycache__", "*.pyc"),
    )
    _copy_import_folders(
        integration_imports_dir / "themes",
        Path(hass.config.path("themes")),
        "themes",
    )
    _copy_import_folders(
        integration_imports_dir / "community",
        Path(hass.config.path("www", "community")),
        "community",
    )


async def async_setup_imports(hass: HomeAssistant, domain: str) -> None:
    """Set up packaged imports."""
    await hass.async_add_executor_job(copy_imports, hass, domain)
    await _async_register_community_resources(hass, domain)
