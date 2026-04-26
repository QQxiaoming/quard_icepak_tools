from tool_model import ToolSpec

from .result_dialog import show_mesh_quality_result
from .tool import DEFAULT_TCL_SCRIPT, generate_mesh_quality_report


def execute_mesh_quality(parameters: dict[str, str], log=None, progress=None):
    return generate_mesh_quality_report(
        input_path=parameters["input_path"],
        icepak_bin=parameters.get("icepak_bin") or None,
        env_script=parameters.get("env_script") or None,
        tcl_script=parameters.get("tcl_script") or None,
        log=log,
        progress=progress,
    )


TOOL_SPEC = ToolSpec(
    key="mesh_generation_quality",
    name="网格生成与质量评估工具",
    description=(
        "调用 Classic Icepak 生成网格，等待网格完成后统计几项常用网格质量指标，"
        "并在结果窗口中展示最小值与最大值。"
    ),
    run_button_text="生成网格并评估",
    parameters=(),
    executor=execute_mesh_quality,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
    success_handler=show_mesh_quality_result,
)
