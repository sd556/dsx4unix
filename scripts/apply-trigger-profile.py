#!/usr/bin/env python3
import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

SECTIONS = ("throttleSettings", "brakeSettings")


class ProfileError(Exception):
    pass


def load_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ProfileError(f"{label} does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must contain a JSON object: {path}")
    return value


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compatible(current, replacement) -> bool:
    if is_number(current) and is_number(replacement):
        return True
    return type(current) is type(replacement)


def forza_sections(config: dict) -> dict:
    try:
        profiles = config["Profiles"]
        forza = profiles["Forza"]
    except (KeyError, TypeError) as exc:
        missing = exc.args[0] if exc.args else "Profiles.Forza"
        raise ProfileError(f"missing or invalid configuration object: {missing}") from exc
    if not isinstance(profiles, dict) or not isinstance(forza, dict):
        raise ProfileError("Profiles and Profiles.Forza must be JSON objects")
    result = {}
    for section in SECTIONS:
        value = forza.get(section)
        if not isinstance(value, dict):
            raise ProfileError(f"Profiles.Forza.{section} must be a JSON object")
        result[section] = value
    return result


def validate_overlay(config_sections: dict, overlay: dict, label: str) -> None:
    if set(overlay) != set(SECTIONS):
        raise ProfileError(f"{label} must contain exactly: {', '.join(SECTIONS)}")
    for section in SECTIONS:
        values = overlay[section]
        if not isinstance(values, dict) or not values:
            raise ProfileError(f"{label}.{section} must be a non-empty JSON object")
        current = config_sections[section]
        for key, replacement in values.items():
            if key not in current:
                raise ProfileError(f"missing configuration key: Profiles.Forza.{section}.{key}")
            if not compatible(current[key], replacement):
                raise ProfileError(
                    f"incompatible value type for Profiles.Forza.{section}.{key}"
                )


def atomic_write_json(path: Path, payload: dict) -> None:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            mode = 0o600
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise ProfileError(f"cannot atomically write {path}: {exc}") from exc


def path_exists(path: Path, label: str) -> bool:
    try:
        path.stat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileError(f"cannot inspect {label} {path}: {exc}") from exc


def parse_state(path: Path, config_sections: dict, preset: dict) -> dict:
    state = load_object(path, "trigger profile state")
    if set(state) != {"version", "active", "normal"}:
        raise ProfileError("trigger profile state has an unsupported schema")
    if type(state["version"]) is not int or state["version"] != 1 or state["active"] != "high":
        raise ProfileError("trigger profile state has an unsupported schema")
    normal = state["normal"]
    if not isinstance(normal, dict):
        raise ProfileError("trigger profile state is missing normal settings")
    if set(normal) != set(SECTIONS):
        raise ProfileError("trigger profile state normal settings must contain exactly the trigger sections")
    for section in SECTIONS:
        values = normal[section]
        if not isinstance(values, dict) or set(values) != set(preset[section]):
            raise ProfileError(
                f"trigger profile state normal settings.{section} keys must exactly match the high preset"
            )
    validate_overlay(config_sections, normal, "trigger profile state normal settings")
    return state


def apply_high(config_path: Path, preset_path: Path, state_path: Path) -> str:
    config = load_object(config_path, "runtime configuration")
    preset = load_object(preset_path, "high preset")
    sections = forza_sections(config)
    validate_overlay(sections, preset, "high preset")

    if path_exists(state_path, "trigger profile state"):
        parse_state(state_path, sections, preset)
    else:
        state = {
            "version": 1,
            "active": "high",
            "normal": {
                section: {key: sections[section][key] for key in preset[section]}
                for section in SECTIONS
            },
        }
        atomic_write_json(state_path, state)

    for section in SECTIONS:
        sections[section].update(preset[section])
    atomic_write_json(config_path, config)
    return f"high trigger profile selected: {config_path}"


def apply_normal(config_path: Path, preset_path: Path, state_path: Path) -> str:
    config = load_object(config_path, "runtime configuration")
    preset = load_object(preset_path, "high preset")
    sections = forza_sections(config)
    validate_overlay(sections, preset, "high preset")

    if not path_exists(state_path, "trigger profile state"):
        return f"normal trigger profile already selected: {config_path}"

    state = parse_state(state_path, sections, preset)
    for section in SECTIONS:
        sections[section].update(state["normal"][section])
    atomic_write_json(config_path, config)
    try:
        state_path.unlink()
    except OSError as exc:
        raise ProfileError(f"configuration restored but cannot remove state {state_path}: {exc}") from exc
    return f"normal trigger profile selected: {config_path}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("high", "normal"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--preset", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "high":
            message = apply_high(args.config, args.preset, args.state)
        else:
            message = apply_normal(args.config, args.preset, args.state)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
