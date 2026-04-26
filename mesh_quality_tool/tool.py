from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from icepak_runtime import build_command, resolve_icepak_bin, resolve_icepak_project
from tool_model import ProgressUpdate, TableData, ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("generate_mesh_quality.tcl")
TABLE_COLUMNS_PREFIX = "__QD_TABLE_COLUMNS__\t"
TABLE_ROW_PREFIX = "__QD_TABLE_ROW__\t"
CONTEXT_PREFIX = "__QD_CONTEXT__\t"
PROGRESS_PREFIX = "__QD_PROGRESS__\t"


@dataclass(frozen=True)
class MeshContextEntry:
    category: str
    key: str
    label: str
    value: str
    unit: str


def resolve_tcl_script(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
    else:
        path = DEFAULT_TCL_SCRIPT

    if not path.exists():
        raise FileNotFoundError(f"Tcl script not found: {path}")
    return path


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _context_lookup(context_entries: list[MeshContextEntry]) -> dict[str, MeshContextEntry]:
    return {f"{entry.category}/{entry.key}": entry for entry in context_entries}


def _metric_lookup(table_data: TableData | None) -> dict[str, dict[str, str]]:
    if table_data is None:
        return {}

    columns = {name: index for index, name in enumerate(table_data.columns)}
    required = ("metric_key", "metric_label", "minimum", "maximum", "unit", "interpretation")
    if any(column not in columns for column in required):
        return {}

    metrics: dict[str, dict[str, str]] = {}
    for row in table_data.rows:
        metric_key = row[columns["metric_key"]]
        metrics[metric_key] = {
            "label": row[columns["metric_label"]],
            "minimum": row[columns["minimum"]],
            "maximum": row[columns["maximum"]],
            "unit": row[columns["unit"]],
            "interpretation": row[columns["interpretation"]],
        }
    return metrics


def build_mesh_guidance_report(
    table_data: TableData | None,
    context_entries: list[MeshContextEntry],
    warnings: list[str],
) -> str:
    context = _context_lookup(context_entries)
    metrics = _metric_lookup(table_data)
    lines: list[str] = []

    lines.append("网格质量诊断与改进建议")
    lines.append("")

    object_count = context.get("model/object_count")
    block_count = context.get("model/block_count")
    grid_type = context.get("mesh/grid_type")
    grid_settings_type = context.get("mesh/grid_settings_type")
    size_x = context.get("mesh/grid_size_x")
    size_y = context.get("mesh/grid_size_y")
    size_z = context.get("mesh/grid_size_z")
    sep_x = context.get("mesh/grid_sep_x")
    sep_y = context.get("mesh/grid_sep_y")
    sep_z = context.get("mesh/grid_sep_z")
    max_elements = context.get("mesh/grid_max_elements")
    smooth_quality = context.get("mesh/grid_tetra_smqual")
    smooth_iters = context.get("mesh/grid_tetra_smiters")
    prism_enabled = context.get("mesh/grid_enable_prism_layer")
    prism_layers = context.get("mesh/grid_tetra_prism_num")
    feature_angle = context.get("mesh/grid_hdm_feature_angle")
    refine_features = context.get("mesh/grid_hdm_refine_features")
    include_all_gaps = context.get("mesh/grid_include_all_gaps")

    lines.append("当前模型与网格参数：")
    if object_count is not None or block_count is not None:
        model_summary = []
        if object_count is not None:
            model_summary.append(f"对象数 {object_count.value}")
        if block_count is not None:
            model_summary.append(f"block 数 {block_count.value}")
        lines.append("- " + "，".join(model_summary))
    if grid_type is not None or grid_settings_type is not None:
        mesh_type_summary = []
        if grid_type is not None:
            mesh_type_summary.append(f"网格类型 {grid_type.value}")
        if grid_settings_type is not None:
            mesh_type_summary.append(f"设置档位 {grid_settings_type.value}")
        lines.append("- " + "，".join(mesh_type_summary))
    if size_x is not None and size_y is not None and size_z is not None:
        unit = size_x.unit or size_y.unit or size_z.unit
        unit_suffix = f" {unit}" if unit else ""
        lines.append(
            f"- 全局尺寸: x={size_x.value}, y={size_y.value}, z={size_z.value}{unit_suffix}"
        )
    if sep_x is not None and sep_y is not None and sep_z is not None:
        unit = sep_x.unit or sep_y.unit or sep_z.unit
        unit_suffix = f" {unit}" if unit else ""
        lines.append(
            f"- 最小分离间隙: x={sep_x.value}, y={sep_y.value}, z={sep_z.value}{unit_suffix}"
        )
    if max_elements is not None:
        lines.append(f"- 最大单元数上限: {max_elements.value}")
    if smooth_quality is not None or smooth_iters is not None:
        smoothing_summary = []
        if smooth_quality is not None:
            smoothing_summary.append(f"平滑质量阈值 {smooth_quality.value}")
        if smooth_iters is not None:
            smoothing_summary.append(f"平滑迭代 {smooth_iters.value}")
        lines.append("- " + "，".join(smoothing_summary))
    if prism_enabled is not None:
        prism_summary = [f"棱柱层 {'开启' if prism_enabled.value == '1' else '关闭'}"]
        if prism_layers is not None:
            prism_summary.append(f"层数 {prism_layers.value}")
        lines.append("- " + "，".join(prism_summary))
    if feature_angle is not None or refine_features is not None or include_all_gaps is not None:
        refinement_summary = []
        if feature_angle is not None:
            refinement_summary.append(f"特征角 {feature_angle.value} deg")
        if refine_features is not None:
            refinement_summary.append(f"特征细化 {'开启' if refine_features.value == '1' else '关闭'}")
        if include_all_gaps is not None:
            refinement_summary.append(f"包含全部窄缝 {'开启' if include_all_gaps.value == '1' else '关闭'}")
        lines.append("- " + "，".join(refinement_summary))

    lines.append("")
    lines.append("质量判断：")

    advice_lines: list[str] = []

    quality_min = _safe_float(metrics.get("det_aspect", {}).get("minimum", ""))
    skewness_max = _safe_float(metrics.get("skewness", {}).get("maximum", ""))
    facealign_min = _safe_float(metrics.get("facealign", {}).get("minimum", ""))
    volume_min = _safe_float(metrics.get("volume", {}).get("minimum", ""))
    grid_size_values = [
        _safe_float(entry.value)
        for entry in (size_x, size_y, size_z)
        if entry is not None
    ]
    sep_values = [
        _safe_float(entry.value)
        for entry in (sep_x, sep_y, sep_z)
        if entry is not None
    ]
    valid_grid_sizes = [value for value in grid_size_values if value is not None and value > 0]
    valid_seps = [value for value in sep_values if value is not None and value > 0]

    if quality_min is not None:
        if quality_min < 0.1:
            lines.append(f"- Quality 最小值 {quality_min:.6g}，明显偏低。")
            advice_lines.append(
                "- 先优先减小全局尺寸或对问题区域做局部加密，当前最差单元形状已经进入明显不稳定区。"
            )
        elif quality_min < 0.2:
            lines.append(f"- Quality 最小值 {quality_min:.6g}，偏低。")
            advice_lines.append(
                "- 建议优先检查几何转角、薄缝和小特征附近的单元，必要时局部收紧网格尺寸。"
            )
        else:
            lines.append(f"- Quality 最小值 {quality_min:.6g}，未见明显异常。")

    if skewness_max is not None:
        if skewness_max > 0.95:
            lines.append(f"- Skewness 最大值 {skewness_max:.6g}，非常高。")
            advice_lines.append(
                "- 高 skewness 往往来自狭窄通道、尖角或尺寸突变，建议减小局部尺寸并提高网格过渡平滑度。"
            )
        elif skewness_max > 0.9:
            lines.append(f"- Skewness 最大值 {skewness_max:.6g}，偏高。")
            advice_lines.append(
                "- 可先尝试适度收紧网格，必要时提高平滑迭代次数，减少畸变单元。"
            )
        else:
            lines.append(f"- Skewness 最大值 {skewness_max:.6g}，在可接受范围内。")

    if facealign_min is not None:
        if facealign_min < 0.1:
            lines.append(f"- Face alignment 最小值 {facealign_min:.6g}，较差。")
            advice_lines.append(
                "- 面对齐偏低通常说明网格在斜面、曲面或薄壁附近对齐不足，可考虑开启特征细化并降低局部尺寸。"
            )
        elif facealign_min < 0.2:
            lines.append(f"- Face alignment 最小值 {facealign_min:.6g}，一般。")
            advice_lines.append(
                "- 如果该区域正好是主要流道或换热路径，建议进一步细化相关表面附近的网格。"
            )
        else:
            lines.append(f"- Face alignment 最小值 {facealign_min:.6g}，基本正常。")

    if volume_min is not None:
        if volume_min <= 0:
            lines.append(f"- Cell volume 最小值 {volume_min:.6g}，存在非正体积风险。")
            advice_lines.append(
                "- 这通常意味着几何重叠、网格穿插或局部尺寸设置过激，建议先检查几何干涉和极小缝隙。"
            )
        else:
            lines.append(f"- Cell volume 最小值 {volume_min:.6g}，保持为正。")

    if valid_grid_sizes and valid_seps:
        coarse_ratio = min(valid_grid_sizes) / min(valid_seps)
        if coarse_ratio > 20:
            advice_lines.append(
                f"- 当前最小全局尺寸与最小分离间隙的比值约为 {coarse_ratio:.3g}，网格相对缝隙偏粗；若问题区域包含窄缝，建议减小全局尺寸或开启更强的局部细化。"
            )
        elif coarse_ratio < 3:
            advice_lines.append(
                f"- 当前最小全局尺寸与最小分离间隙的比值约为 {coarse_ratio:.3g}，网格已经较细；若质量仍差，更应优先检查几何尖角、重叠和拓扑复杂区，而不是继续盲目加密。"
            )

    if max_elements is not None:
        max_elements_value = _safe_float(max_elements.value)
        if max_elements_value is not None and max_elements_value < 1_000_000:
            advice_lines.append(
                f"- 当前最大单元数上限仅为 {max_elements.value}，如果模型对象较多，可能提前限制了局部细化能力。"
            )

    if smooth_quality is not None:
        smooth_quality_value = _safe_float(smooth_quality.value)
        if smooth_quality_value is not None and smooth_quality_value < 0.5 and skewness_max is not None and skewness_max > 0.9:
            advice_lines.append(
                f"- 当前平滑质量阈值为 {smooth_quality.value}，在 skewness 偏高时可尝试适度提高该阈值，并配合增加平滑迭代次数。"
            )
    if smooth_iters is not None:
        smooth_iters_value = _safe_float(smooth_iters.value)
        if smooth_iters_value is not None and smooth_iters_value < 15 and skewness_max is not None and skewness_max > 0.9:
            advice_lines.append(
                f"- 当前平滑迭代只有 {smooth_iters.value} 次，如果畸变单元集中在局部复杂区，可尝试上调平滑迭代。"
            )

    if prism_enabled is not None and prism_enabled.value == "0" and facealign_min is not None and facealign_min < 0.2:
        advice_lines.append(
            "- 当前棱柱层未开启；如果低质量区域主要出现在壁面边界层附近，可以考虑启用棱柱层而不是只做体网格加密。"
        )

    if refine_features is not None and refine_features.value == "0" and quality_min is not None and quality_min < 0.2:
        advice_lines.append(
            "- 当前特征细化未开启，而 Quality 已偏低；如果模型含尖角、小孔、切角或薄片边缘，建议开启特征细化。"
        )

    if include_all_gaps is not None and include_all_gaps.value == "0" and valid_seps:
        advice_lines.append(
            "- 当前未开启全部窄缝包含；若低质量区域与窄缝、缝隙导流有关，建议针对该类区域重新评估 gap 捕捉策略。"
        )

    if warnings:
        lines.append("")
        lines.append("网格日志告警：")
        for warning in warnings:
            lines.append(f"- {warning}")

        modified_gap_warning = any("minimum separation" in warning for warning in warnings)
        intersect_warning = any("intersects assembly" in warning for warning in warnings)
        if modified_gap_warning:
            advice_lines.append(
                "- 日志显示存在小于最小分离阈值的缝隙被自动调整，这通常说明当前几何最小缝隙已经接近或小于网格分离参数，需要联合检查 sep_x/sep_y/sep_z 与真实缝隙尺度。"
            )
        if intersect_warning:
            advice_lines.append(
                "- 日志显示对象边界与装配边界相交，建议先排查几何相交或接触关系；这类问题往往比单纯调网格参数更影响质量。"
            )

    lines.append("")
    lines.append("改进建议：")
    if advice_lines:
        lines.extend(advice_lines)
    else:
        lines.append("- 当前四项指标未显示出明显的低质量风险，暂时不建议为了追求更小数值而盲目继续加密。")

    return "\n".join(lines)


def generate_mesh_quality_report(
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
    if progress is not None:
        progress(ProgressUpdate(mode="indeterminate", message="正在准备网格生成与质量评估..."))

    columns: list[str] = []
    rows: list[tuple[str, ...]] = []
    context_entries: list[MeshContextEntry] = []
    warnings: list[str] = []

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
        if stripped.startswith(CONTEXT_PREFIX):
            parts = stripped[len(CONTEXT_PREFIX) :].split("\t")
            if len(parts) >= 5:
                context_entries.append(
                    MeshContextEntry(
                        category=parts[0],
                        key=parts[1],
                        label=parts[2],
                        value=parts[3],
                        unit=parts[4],
                    )
                )
            continue

        lowered = stripped.casefold()
        if "warning:" in lowered or "intersects assembly" in lowered or "minimum separation" in lowered:
            warnings.append(stripped)
        logger(stripped)

    exit_code = process.wait()
    table_data = None
    if columns:
        table_data = TableData(
            columns=tuple(columns),
            rows=tuple(rows),
            default_export_name="mesh_quality_metrics.csv",
        )
    report_text = build_mesh_guidance_report(table_data, context_entries, warnings)
    if progress is not None:
        progress(ProgressUpdate(mode="determinate", value=99, maximum=100, message="网格质量评估完成，正在整理结果..."))
    return ToolExecutionResult(exit_code=exit_code, table_data=table_data, report_text=report_text)
