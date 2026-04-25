from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path
from tool_model import ParameterSpec, ToolSpec, build_output_path


def discover_tools() -> list[ToolSpec]:
    # When packaged with PyInstaller, sys.frozen is True and sys._MEIPASS holds
    # the temporary directory where bundled files are extracted at runtime.
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        workspace_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    else:
        workspace_root = Path(__file__).resolve().parent
    tools: list[ToolSpec] = []

    for child in sorted(workspace_root.iterdir()):
        if not child.is_dir() or not child.name.endswith("_tool"):
            continue

        if not is_frozen:
            # In normal runs, require manifest.py or manifest.pyc on disk to preserve
            # local-discovery-only behavior and avoid importing unrelated packages.
            if not (child / "manifest.py").exists() and not (child / "manifest.pyc").exists():
                continue

        try:
            module = importlib.import_module(f"{child.name}.manifest")
        except ImportError:
            continue

        tool_spec = getattr(module, "TOOL_SPEC", None)
        if tool_spec is None:
            continue
        tools.append(tool_spec)

    return tools


TOOLS = discover_tools()


def default_env_script_path() -> str:
    workspace_root = Path(__file__).resolve().parent
    if platform.system().lower() == "windows":
        local_bat = workspace_root / "ansys_env.bat"
        if local_bat.exists():
            return str(local_bat)
        return str(Path.home() / "ansys_env.bat")

    return str(Path.home() / "ansys-v221-env.sh")


SHARED_PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        key="env_script",
        label="Ansys 环境脚本",
        browse_mode="open_file",
        required=False,
        file_filter="Scripts (*.sh *.bat *.cmd);;All Files (*)",
        default_value=default_env_script_path(),
    ),
    ParameterSpec(
        key="input_path",
        label="测试用例路径",
        browse_mode="project_path",
        required=True,
        file_filter="Workbench Project (*.wbpj);;All Files (*)",
        default_value=str(Path.cwd() / "test" / "01.wbpj"),
    ),
)


def get_tool(tool_key: str) -> ToolSpec:
    for tool in TOOLS:
        if tool.key == tool_key:
            return tool
    raise KeyError(f"Unknown tool: {tool_key}")