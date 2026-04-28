from tool_model import ToolSpec

from .result_dialog import show_model_tree_result
from .tool import DEFAULT_TCL_SCRIPT, export_model_tree_preview
from .tool_version import TOOL_VERSION


def execute_model_tree_preview(parameters: dict[str, str], log=None, progress=None):
    return export_model_tree_preview(
        input_path=parameters["input_path"],
        icepak_bin=parameters.get("icepak_bin") or None,
        env_script=parameters.get("env_script") or None,
        tcl_script=parameters.get("tcl_script") or None,
        log=log,
        progress=progress,
    )


TOOL_SPEC = ToolSpec(
    key="icepak_model_tree_preview",
    name="Icepak 模型树预览工具",
    version=TOOL_VERSION,
    description="加载 Classic Icepak 工程，并按 Icepak 官方模型树父子关系预览对象层级。",
    run_button_text="加载模型树",
    parameters=(),
    executor=execute_model_tree_preview,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
    success_handler=show_model_tree_result,
)