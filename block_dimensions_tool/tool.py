from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from tool_model import TableData, ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("print_block_dimensions.tcl")
TABLE_COLUMNS_PREFIX = "__QD_TABLE_COLUMNS__\t"
TABLE_ROW_PREFIX = "__QD_TABLE_ROW__\t"


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


def candidate_icepak_bins() -> list[Path]:
    system = platform.system().lower()
    candidates: list[Path] = []

    awp_root = os.environ.get("AWP_ROOT221")
    if awp_root:
        awp = Path(awp_root)
        candidates.extend(
            [
                awp / "Icepak" / "bin" / "icepak",
                awp / "Icepak" / "bin" / "icepak.bat",
                awp / "Icepak" / "bin" / "winx64" / "icepak.exe",
                awp / "Icepak" / "icepak22.1" / "bin.lnamd64" / "icepak",
            ]
        )

    if system == "windows":
        candidates.extend(
            [
                Path(r"C:\Program Files\ANSYS Inc\v221\Icepak\bin\icepak.bat"),
                Path(r"C:\Program Files\ANSYS Inc\v221\Icepak\bin\winx64\icepak.exe"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("/usr/ansys_inc/v221/Icepak/bin/icepak"),
                Path("/usr/ansys_inc/v221/Icepak/icepak22.1/bin.lnamd64/icepak"),
            ]
        )

    which_hit = shutil.which("icepak")
    if which_hit:
        candidates.append(Path(which_hit))

    return candidates


def resolve_icepak_bin(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Icepak executable not found: {path}")
        return path

    for candidate in candidate_icepak_bins():
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Unable to locate Classic Icepak. Set AWP_ROOT221 or pass an explicit launcher path."
    )


def resolve_tcl_script(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
    else:
        path = DEFAULT_TCL_SCRIPT

    if not path.exists():
        raise FileNotFoundError(f"Tcl script not found: {path}")
    return path


def build_command(
    icepak_bin: Path,
    macro_path: Path,
    project_dir: Path,
    env_script: str | None,
) -> list[str]:
    if not env_script:
        return [str(icepak_bin), "-batch", "-run_script", str(macro_path), str(project_dir)]

    env_path = Path(env_script).expanduser().resolve()
    if not env_path.exists():
        raise FileNotFoundError(f"环境脚本不存在：{env_path}")

    suffix = env_path.suffix.lower()
    if suffix == ".sh":
        command = (
            f'source "{env_path}" && '
            f'exec "{icepak_bin}" -batch -run_script "{macro_path}" "{project_dir}"'
        )
        return ["bash", "-lc", command]

    if suffix in {".bat", ".cmd"}:
        command = (
            f'call "{env_path}" && '
            f'"{icepak_bin}" -batch -run_script "{macro_path}" "{project_dir}"'
        )
        return ["cmd.exe", "/c", command]

    raise ValueError("环境脚本必须以 .sh、.bat 或 .cmd 结尾")


def export_block_dimensions(
    input_path: str | Path,
    icepak_bin: str | None = None,
    env_script: str | None = None,
    tcl_script: str | None = None,
    log: Callable[[str], None] | None = None,
) -> ToolExecutionResult:
    logger = log or print

    project_dir = resolve_icepak_project(Path(input_path))
    resolved_icepak_bin = resolve_icepak_bin(icepak_bin)
    resolved_tcl_script = resolve_tcl_script(tcl_script)

    command = build_command(
        resolved_icepak_bin,
        resolved_tcl_script,
        project_dir,
        env_script,
    )

    logger(f"Icepak 工程：{project_dir}")
    logger(f"Icepak 可执行文件：{resolved_icepak_bin}")
    logger(f"Tcl 脚本：{resolved_tcl_script}")

    columns: list[str] = []
    rows: list[tuple[str, ...]] = []

    process = subprocess.Popen(
        command,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.rstrip()
        if stripped.startswith(TABLE_COLUMNS_PREFIX):
            columns = stripped[len(TABLE_COLUMNS_PREFIX) :].split("\t")
            continue
        if stripped.startswith(TABLE_ROW_PREFIX):
            rows.append(tuple(stripped[len(TABLE_ROW_PREFIX) :].split("\t")))
            continue
        logger(stripped)

    exit_code = process.wait()
    table_data = None
    if columns:
        table_data = TableData(
            columns=tuple(columns),
            rows=tuple(rows),
            default_export_name="block_dimensions.csv",
        )
    return ToolExecutionResult(exit_code=exit_code, table_data=table_data)
