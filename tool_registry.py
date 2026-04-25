from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from tool_model import ParameterSpec, ToolSpec, build_output_path


def discover_tools() -> list[ToolSpec]:
    # When packaged with PyInstaller, sys.frozen is True and sys._MEIPASS holds
    # the temporary directory where bundled files are extracted at runtime.
    if getattr(sys, "frozen", False):
        workspace_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    else:
        workspace_root = Path(__file__).resolve().parent
    tools: list[ToolSpec] = []

    for child in sorted(workspace_root.iterdir()):
        if not child.is_dir() or not child.name.endswith("_tool"):
            continue
        has_manifest = (
            (child / "manifest.py").exists()
            or (child / "manifest.pyc").exists()
            or importlib.util.find_spec(f"{child.name}.manifest") is not None
        )
        if not has_manifest:
            continue

        module = importlib.import_module(f"{child.name}.manifest")
        tool_spec = getattr(module, "TOOL_SPEC", None)
        if tool_spec is None:
            continue
        tools.append(tool_spec)

    return tools


TOOLS = discover_tools()


SHARED_PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        key="env_script",
        label="Ansys 环境脚本",
        browse_mode="open_file",
        required=True,
        file_filter="Scripts (*.sh *.bat *.cmd);;All Files (*)",
        default_value=str(Path.home() / "ansys-v221-env.sh"),
    ),
    ParameterSpec(
        key="input_path",
        label="测试用例路径",
        browse_mode="project_path",
        required=True,
        file_filter="Workbench Project (*.wbpj);;All Files (*)",
        default_value=str(Path.cwd() / "test" / "01.wbpj"),
    ),
    ParameterSpec(
        key="icepak_bin",
        label="Icepak 可执行文件",
        browse_mode="open_file",
        required=False,
        file_filter="Executables (*)",
    ),
)


def get_tool(tool_key: str) -> ToolSpec:
    for tool in TOOLS:
        if tool.key == tool_key:
            return tool
    raise KeyError(f"Unknown tool: {tool_key}")