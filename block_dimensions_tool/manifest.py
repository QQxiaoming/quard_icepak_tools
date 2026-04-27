from tool_model import ToolSpec

from .result_dialog import show_block_dimensions_result
from .tool import DEFAULT_TCL_SCRIPT, export_block_dimensions
from .tool_version import TOOL_VERSION

def execute_block_dimensions(parameters: dict[str, str], log=None, progress=None) -> int:
    return export_block_dimensions(
        input_path=parameters["input_path"],
        icepak_bin=parameters.get("icepak_bin") or None,
        env_script=parameters.get("env_script") or None,
        tcl_script=parameters.get("tcl_script") or None,
        log=log,
        progress=progress,
    )


TOOL_SPEC = ToolSpec(
    key="block_dimensions_csv",
    name="Block 尺寸统计工具",
    version=TOOL_VERSION,
    description=(
        "加载 Classic Icepak 工程，并在界面中显示各个 block 的尺寸和包围盒坐标。"
    ),
    run_button_text="开始统计",
    parameters=(),
    executor=execute_block_dimensions,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
    success_handler=show_block_dimensions_result,
)