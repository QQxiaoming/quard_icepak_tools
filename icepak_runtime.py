from __future__ import annotations

import os
import platform
import re
import shutil
from pathlib import Path


def resolve_icepak_project(input_path: Path) -> Path:
    candidate = input_path.resolve()

    if candidate.is_dir() and (candidate / "model").is_file():
        return candidate

    if candidate.is_file() and candidate.suffix.lower() == ".wbpj":
        files_dir = candidate.with_name(candidate.stem + "_files")
        if files_dir.is_dir():
            matches = sorted(files_dir.rglob("IcepakProj"))
            if matches:
                return matches[0]

    if candidate.is_dir():
        matches = sorted(candidate.rglob("IcepakProj"))
        if matches:
            return matches[0]

    raise FileNotFoundError(f"IcepakProj directory not found from input: {input_path}")


def _parse_env_script(env_script: str | None) -> dict[str, str]:
    if not env_script:
        return {}

    env_path = Path(env_script).expanduser().resolve()
    if not env_path.exists():
        return {}

    if env_path.suffix.lower() in {".bat", ".cmd"}:
        pattern = re.compile(r"^\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$", re.IGNORECASE)
    elif env_path.suffix.lower() == ".sh":
        pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$")
    else:
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("rem "):
            continue

        match = pattern.match(line)
        if not match:
            continue

        key, value = match.groups()
        cleaned_value = value.strip().strip('"')
        if cleaned_value:
            values[key] = cleaned_value

    return values


def _version_key(root: Path) -> tuple[int, str]:
    match = re.fullmatch(r"v(\d+)", root.name, re.IGNORECASE)
    if not match:
        return (0, root.name)
    return (int(match.group(1)), root.name)


def _release_tag(root: Path) -> str | None:
    match = re.fullmatch(r"v(\d+)", root.name, re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def _version_tag(root: Path) -> str | None:
    release_tag = _release_tag(root)
    if not release_tag or len(release_tag) < 3:
        return None
    return f"{release_tag[:-1]}.{release_tag[-1]}"


def _iter_awp_roots(extra_env: dict[str, str]) -> list[Path]:
    merged_env = os.environ.copy()
    merged_env.update(extra_env)

    roots: dict[str, Path] = {}
    for key, value in merged_env.items():
        if re.fullmatch(r"AWP_ROOT\d+", key, re.IGNORECASE) and value:
            roots[str(Path(value))] = Path(value)

    for key, value in merged_env.items():
        if not re.fullmatch(r"ANSYS\d+_DIR", key, re.IGNORECASE) or not value:
            continue
        ansys_dir = Path(value)
        candidate_root = ansys_dir.parent
        if re.fullmatch(r"v\d+", candidate_root.name, re.IGNORECASE):
            roots[str(candidate_root)] = candidate_root

    system = platform.system().lower()
    if system == "windows":
        base_dir = Path(r"C:\Program Files\ANSYS Inc")
    else:
        base_dir = Path("/usr/ansys_inc")

    if base_dir.exists():
        for child in base_dir.iterdir():
            if child.is_dir() and re.fullmatch(r"v\d+", child.name, re.IGNORECASE):
                roots.setdefault(str(child), child)

    return sorted(roots.values(), key=_version_key, reverse=True)


def _candidate_bins_for_root(root: Path, system: str) -> list[Path]:
    version_tag = _version_tag(root)
    candidates = [
        root / "Icepak" / "bin" / "icepak",
        root / "Icepak" / "bin" / "icepak.bat",
        root / "Icepak" / "bin" / "winx64" / "icepak.exe",
    ]

    if not version_tag:
        return candidates

    if system == "windows":
        candidates.extend(
            [
                root / "Icepak" / "bin" / f"icepak{version_tag}win64.bat",
                root / "Icepak" / f"icepak{version_tag}" / "bin.win64_amd" / "icepak.exe",
                root / "Icepak" / f"icepak{version_tag}" / "bin.win64_amd" / "icepak_batch.exe",
            ]
        )
    else:
        candidates.append(root / "Icepak" / f"icepak{version_tag}" / "bin.lnamd64" / "icepak")

    return candidates


def candidate_icepak_bins(env_script: str | None = None) -> list[Path]:
    system = platform.system().lower()
    candidates: list[Path] = []

    for awp_root in _iter_awp_roots(_parse_env_script(env_script)):
        candidates.extend(_candidate_bins_for_root(awp_root, system))

    which_hit = shutil.which("icepak")
    if which_hit:
        candidates.append(Path(which_hit))

    # Preserve candidate order while dropping duplicates.
    return list(dict.fromkeys(candidates))


def resolve_icepak_bin(explicit: str | None, env_script: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Icepak executable not found: {path}")
        return path

    for candidate in candidate_icepak_bins(env_script):
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Unable to locate Classic Icepak. Set an AWP_ROOTxxx variable, provide an env script, or pass an explicit launcher path."
    )


def build_command(
    icepak_bin: Path,
    macro_path: Path,
    project_dir: Path,
    env_script: str | None,
) -> list[str]:
    icepak_args = f'-batch -run_script "{macro_path}" "{project_dir}"'

    if platform.system().lower() == "windows" and icepak_bin.suffix.lower() in {".bat", ".cmd"}:
        launch_icepak = f'call "{icepak_bin}" {icepak_args}'
    else:
        launch_icepak = f'"{icepak_bin}" {icepak_args}'

    if not env_script:
        if platform.system().lower() == "windows" and icepak_bin.suffix.lower() in {".bat", ".cmd"}:
            return ["cmd.exe", "/d", "/s", "/c", launch_icepak]
        return [str(icepak_bin), "-batch", "-run_script", str(macro_path), str(project_dir)]

    env_path = Path(env_script).expanduser().resolve()
    if not env_path.exists():
        raise FileNotFoundError(f"环境脚本不存在：{env_path}")

    suffix = env_path.suffix.lower()
    if suffix == ".sh":
        command = (
            f'source "{env_path}" && '
            f'exec "{icepak_bin}" {icepak_args}'
        )
        return ["bash", "-lc", command]

    if suffix in {".bat", ".cmd"}:
        command = f'call "{env_path}" && {launch_icepak}'
        return ["cmd.exe", "/d", "/s", "/c", command]

    raise ValueError("环境脚本必须以 .sh、.bat 或 .cmd 结尾")