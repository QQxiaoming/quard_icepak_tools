from __future__ import annotations

from pathlib import Path
from typing import Callable

from tool_model import ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("example_tool.tcl")


def run_example_tool(
    parameters: dict[str, str],
    log: Callable[[str], None] | None = None,
) -> ToolExecutionResult:
    logger = log or print

    tool_name = parameters.get("tool_name", "example_tool")
    case_path = Path(parameters["input_path"]).expanduser().resolve()
    note = parameters.get("note", "")
    tcl_script = parameters.get("tcl_script", "")

    lines = [
        "# Icepak Example Tool Output",
        "",
        f"tool_name: {tool_name}",
        f"input_path: {case_path}",
        f"tcl_script: {tcl_script or '<not set>'}",
        f"note: {note or '<empty>'}",
        "",
        "This is a template tool entry used to demonstrate how to add new tools to the GUI registry.",
        "Replace run_example_tool with real execution logic when you add the next Icepak automation flow.",
    ]

    logger(f"模板工具名称：{tool_name}")
    logger(f"输入路径：{case_path}")
    if tcl_script:
        logger(f"模板 Tcl 路径：{Path(tcl_script).expanduser()}")
    if note:
        logger(f"备注：{note}")
    logger("模板工具执行成功。")

    return ToolExecutionResult(exit_code=0)
