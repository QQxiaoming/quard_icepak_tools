from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from icepak_runtime import build_command, resolve_icepak_bin, resolve_icepak_project
from tool_model import TableData, ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("print_block_dimensions.tcl")
TABLE_COLUMNS_PREFIX = "__QD_TABLE_COLUMNS__\t"
TABLE_ROW_PREFIX = "__QD_TABLE_ROW__\t"

def resolve_tcl_script(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
    else:
        path = DEFAULT_TCL_SCRIPT

    if not path.exists():
        raise FileNotFoundError(f"Tcl script not found: {path}")
    return path

def export_block_dimensions(
    input_path: str | Path,
    icepak_bin: str | None = None,
    env_script: str | None = None,
    tcl_script: str | None = None,
    log: Callable[[str], None] | None = None,
) -> ToolExecutionResult:
    logger = log or print

    project_dir = resolve_icepak_project(Path(input_path))
    resolved_icepak_bin = resolve_icepak_bin(icepak_bin, env_script)
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
