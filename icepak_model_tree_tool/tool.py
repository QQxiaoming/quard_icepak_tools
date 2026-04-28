from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from icepak_runtime import build_command, resolve_icepak_bin, resolve_icepak_project
from tool_model import ProgressUpdate, TableData, ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("preview_model_tree.tcl")
TABLE_COLUMNS_PREFIX = "__QD_TABLE_COLUMNS__\t"
TABLE_ROW_PREFIX = "__QD_TABLE_ROW__\t"
PROGRESS_PREFIX = "__QD_PROGRESS__\t"


def export_model_tree_preview(
    input_path: str | Path,
    icepak_bin: str | None = None,
    env_script: str | None = None,
    tcl_script: str | None = None,
    log: Callable[[str], None] | None = None,
    progress: Callable[[ProgressUpdate], None] | None = None,
) -> ToolExecutionResult:
    logger = log or print
    project_dir = resolve_icepak_project(Path(input_path))
    resolved_icepak_bin = resolve_icepak_bin(icepak_bin, env_script)
    resolved_tcl_script = Path(tcl_script).expanduser().resolve() if tcl_script else DEFAULT_TCL_SCRIPT
    if not resolved_tcl_script.exists():
        raise FileNotFoundError(f"Tcl script not found: {resolved_tcl_script}")

    command = build_command(
        resolved_icepak_bin,
        resolved_tcl_script,
        project_dir,
        env_script,
    )

    logger(f"Icepak 工程：{project_dir}")
    logger(f"Icepak 可执行文件：{resolved_icepak_bin}")
    logger(f"Tcl 脚本：{resolved_tcl_script}")
    if progress is not None:
        progress(ProgressUpdate(mode="indeterminate", message="正在加载 Icepak 模型树预览..."))

    columns: list[str] = []
    rows: list[tuple[str, ...]] = []

    process = subprocess.Popen(
        command,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.rstrip()
        if stripped.startswith(PROGRESS_PREFIX):
            parts = stripped[len(PROGRESS_PREFIX) :].split("\t")
            if len(parts) >= 4 and progress is not None:
                mode, value, maximum, message = parts[:4]
                if mode == "determinate":
                    progress(
                        ProgressUpdate(
                            mode="determinate",
                            value=int(value),
                            maximum=int(maximum),
                            message=message,
                        )
                    )
                elif mode == "indeterminate":
                    progress(ProgressUpdate(mode="indeterminate", message=message))
            continue
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
            default_export_name="icepak_model_tree.csv",
        )
    if progress is not None:
        progress(ProgressUpdate(mode="determinate", value=100, maximum=100, message="Icepak 模型树预览完成"))
    return ToolExecutionResult(exit_code=exit_code, table_data=table_data)