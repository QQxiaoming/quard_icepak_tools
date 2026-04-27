from __future__ import annotations

import importlib
import hashlib
import importlib.util
import platform
import re
import shutil
import sys
import tempfile
import traceback
import types
import zipfile
from dataclasses import replace
from pathlib import Path, PurePosixPath

from tool_model import ParameterSpec, ToolSpec, build_output_path


_DYNAMIC_NAMESPACE = "_quard_dynamic_tools"
_CUSTOM_TOOL_APP_DIR = "QuardIcepakTools"


class ToolLoadError(Exception):
    def __init__(self, summary: str, details: str = "") -> None:
        super().__init__(summary)
        self.summary = summary
        self.details = details


def workspace_root() -> Path:
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return Path(__file__).resolve().parent


def _user_data_base_dir() -> Path:
    system_name = platform.system().lower()
    if system_name == "windows":
        return Path.home() / "AppData" / "Roaming"
    if system_name == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".local" / "share"


def user_tool_root() -> Path:
    base_dir = _user_data_base_dir()
    target_dir = base_dir / _CUSTOM_TOOL_APP_DIR / "custom_tools"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _tool_sort_key(tool: ToolSpec) -> tuple[bool, str]:
    return (not tool.is_builtin, tool.key == "example_template", tool.name.casefold())


def _ensure_namespace_package() -> None:
    if _DYNAMIC_NAMESPACE in sys.modules:
        return

    module = types.ModuleType(_DYNAMIC_NAMESPACE)
    module.__path__ = []
    module.__package__ = _DYNAMIC_NAMESPACE
    module.__spec__ = importlib.util.spec_from_loader(_DYNAMIC_NAMESPACE, loader=None, is_package=True)
    sys.modules[_DYNAMIC_NAMESPACE] = module


def _purge_module_prefix(prefix: str) -> None:
    for module_name in list(sys.modules):
        if module_name == prefix or module_name.startswith(f"{prefix}."):
            del sys.modules[module_name]


def _module_prefix_for_tool(tool_dir: Path) -> str:
    digest = hashlib.sha1(str(tool_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"{_DYNAMIC_NAMESPACE}.{tool_dir.name}_{digest}"


def _load_builtin_tool_spec(tool_dir: Path) -> ToolSpec | None:
    try:
        module = importlib.import_module(f"{tool_dir.name}.manifest")
    except Exception:
        return None

    tool_spec = getattr(module, "TOOL_SPEC", None)
    if not isinstance(tool_spec, ToolSpec):
        return None

    return replace(tool_spec, source_path=str(tool_dir), is_builtin=True)


def _load_tool_spec_from_directory(
    tool_dir: Path,
    *,
    is_builtin: bool,
    error_summary: str | None = None,
) -> ToolSpec | None:
    manifest_path = tool_dir / "manifest.py"
    if is_builtin:
        builtin_tool = _load_builtin_tool_spec(tool_dir)
        if builtin_tool is not None:
            return builtin_tool

    if not manifest_path.exists():
        return None

    _ensure_namespace_package()
    module_prefix = _module_prefix_for_tool(tool_dir)
    _purge_module_prefix(module_prefix)
    package_leaf = module_prefix.rsplit(".", 1)[-1]

    package_module = types.ModuleType(module_prefix)
    package_module.__path__ = [str(tool_dir)]
    package_module.__package__ = module_prefix
    package_module.__spec__ = importlib.util.spec_from_loader(module_prefix, loader=None, is_package=True)
    sys.modules[module_prefix] = package_module
    setattr(sys.modules[_DYNAMIC_NAMESPACE], package_leaf, package_module)

    spec = importlib.util.spec_from_file_location(f"{module_prefix}.manifest", manifest_path)
    if spec is None or spec.loader is None:
        _purge_module_prefix(module_prefix)
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        _purge_module_prefix(module_prefix)
        if error_summary is not None:
            details = (
                f"manifest 路径：{manifest_path}\n"
                f"异常类型：{type(exc).__name__}\n"
                f"异常信息：{exc}\n\n"
                f"详细堆栈：\n{traceback.format_exc()}"
            )
            raise ToolLoadError(error_summary, details) from exc
        return None

    tool_spec = getattr(module, "TOOL_SPEC", None)
    if not isinstance(tool_spec, ToolSpec):
        _purge_module_prefix(module_prefix)
        if error_summary is not None:
            details = (
                f"manifest 路径：{manifest_path}\n"
                "manifest.py 没有导出合法的 TOOL_SPEC。\n"
                "要求：顶层变量 TOOL_SPEC 必须是 ToolSpec 实例。"
            )
            raise ToolLoadError(error_summary, details)
        return None

    return replace(tool_spec, source_path=str(tool_dir), is_builtin=is_builtin)


def _iter_tool_directories(root_dir: Path) -> list[Path]:
    if not root_dir.exists():
        return []
    return [child for child in sorted(root_dir.iterdir()) if child.is_dir() and child.name.endswith("_tool")]


def _collect_tools_from_root(root_dir: Path, *, is_builtin: bool) -> list[ToolSpec]:
    tools: list[ToolSpec] = []
    for child in _iter_tool_directories(root_dir):
        tool_spec = _load_tool_spec_from_directory(child, is_builtin=is_builtin)
        if tool_spec is not None:
            tools.append(tool_spec)
    return tools


def _validate_unique_tool_key(candidate: ToolSpec, destination_dir: Path | None = None) -> None:
    for tool in discover_tools():
        if destination_dir is not None and tool.source_path == str(destination_dir):
            continue
        if tool.identifier == candidate.identifier:
            raise ValueError(f"工具 key/version 冲突：{candidate.identifier}")


def _sanitize_tool_dir_name(name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not safe_name:
        safe_name = "custom_tool"
    if not safe_name.endswith("_tool"):
        safe_name = f"{safe_name}_tool"
    return safe_name


def _extract_zip_to_staging(zip_path: Path, staging_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        member_names = [name for name in archive.namelist() if name and not name.endswith("/")]
        if not member_names:
            raise ValueError("zip 压缩包为空。")

        for member_name in member_names:
            member_path = PurePosixPath(member_name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("zip 压缩包中包含非法路径。")

        top_level_entries = {
            PurePosixPath(name).parts[0]
            for name in member_names
            if not name.startswith("__MACOSX/")
        }

        archive.extractall(staging_dir)

    tool_dirs = [staging_dir / entry for entry in sorted(top_level_entries) if (staging_dir / entry).is_dir()]
    matching_dirs = [entry for entry in tool_dirs if entry.name.endswith("_tool")]
    if len(matching_dirs) == 1:
        return matching_dirs[0]

    root_manifest = staging_dir / "manifest.py"
    if root_manifest.exists():
        normalized_dir = staging_dir / _sanitize_tool_dir_name(zip_path.stem)
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for child in list(staging_dir.iterdir()):
            if child == normalized_dir:
                continue
            shutil.move(str(child), str(normalized_dir / child.name))
        return normalized_dir

    raise ValueError("zip 中必须包含一个 *_tool 目录，或在根目录直接包含 manifest.py。")


def install_tool_zip(zip_file_path: str) -> ToolSpec:
    zip_path = Path(zip_file_path).expanduser().resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"找不到 zip 文件：{zip_path}")

    custom_root = user_tool_root()
    with tempfile.TemporaryDirectory(prefix="quard_tool_install_") as temp_dir:
        staging_root = Path(temp_dir)
        staged_tool_dir = _extract_zip_to_staging(zip_path, staging_root)
        tool_spec = _load_tool_spec_from_directory(
            staged_tool_dir,
            is_builtin=False,
            error_summary="无法加载自定义工具的 manifest.py。",
        )
        if tool_spec is None:
            raise ValueError("无法从 zip 中加载 TOOL_SPEC，请检查 manifest.py。")

        destination_dir = custom_root / staged_tool_dir.name
        if destination_dir.exists():
            raise FileExistsError(f"目标工具目录已存在：{destination_dir.name}")

        _validate_unique_tool_key(tool_spec)
        shutil.move(str(staged_tool_dir), str(destination_dir))

    installed_tool = _load_tool_spec_from_directory(
        destination_dir,
        is_builtin=False,
        error_summary="工具已安装，但重新加载 manifest.py 失败。",
    )
    if installed_tool is None:
        raise ValueError("工具已复制，但重新加载失败。")
    return installed_tool


def uninstall_tool(tool: ToolSpec) -> None:
    if tool.is_builtin:
        raise ValueError("内置工具不支持卸载。")

    tool_path = Path(tool.source_path).expanduser().resolve()
    custom_root = user_tool_root().resolve()
    if custom_root not in tool_path.parents:
        raise ValueError("只允许卸载用户安装目录中的工具。")
    if not tool_path.exists():
        raise FileNotFoundError(f"找不到工具目录：{tool_path}")

    shutil.rmtree(tool_path)


def discover_tools() -> list[ToolSpec]:
    tools = _collect_tools_from_root(workspace_root(), is_builtin=True)
    tools.extend(_collect_tools_from_root(user_tool_root(), is_builtin=False))
    tools.sort(key=_tool_sort_key)
    return tools


TOOLS = discover_tools()


SHARED_PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        key="env_script",
        label="Ansys 环境脚本",
        browse_mode="open_file",
        required=False,
        file_filter="Scripts (*.sh *.bat *.cmd);;All Files (*)",
    ),
    ParameterSpec(
        key="input_path",
        label="测试用例路径",
        browse_mode="project_path",
        required=True,
        file_filter="Workbench Project (*.wbpj);;All Files (*)",
    ),
)


def get_tool(tool_id: str) -> ToolSpec:
    for tool in TOOLS:
        if tool.identifier == tool_id:
            return tool
    matches = [tool for tool in TOOLS if tool.key == tool_id]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(f"Unknown tool: {tool_id}")