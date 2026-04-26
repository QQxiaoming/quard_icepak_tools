from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from icepak_runtime import build_command, resolve_icepak_bin, resolve_icepak_project
from tool_model import ProgressUpdate, TableData, ToolExecutionResult


DEFAULT_LIST_TCL_SCRIPT = Path(__file__).resolve().with_name("list_blocks.tcl")
DEFAULT_ADJUST_TCL_SCRIPT = Path(__file__).resolve().with_name("adjust_pair_dz.tcl")
TABLE_COLUMNS_PREFIX = "__QD_TABLE_COLUMNS__\t"
TABLE_ROW_PREFIX = "__QD_TABLE_ROW__\t"
PROGRESS_PREFIX = "__QD_PROGRESS__\t"
EPSILON_MM = 1.0e-6


@dataclass(frozen=True)
class BlockRecord:
    object_name: str
    object_type: str
    shape_name: str
    shape_type: str
    length_unit: str
    dx: float
    dy: float
    dz: float
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float


@dataclass(frozen=True)
class PairAdjustmentPlan:
    selected: BlockRecord
    partner: BlockRecord
    stack_axis: str
    direction_sign: str
    delta_mm: float
    new_shared_coordinate: float
    new_selected_thickness: float
    new_partner_thickness: float


def resolve_tcl_script(explicit: str | None, default: Path) -> Path:
    path = Path(explicit).expanduser().resolve() if explicit else default
    if not path.exists():
        raise FileNotFoundError(f"Tcl script not found: {path}")
    return path


def _run_icepak_script(
    *,
    input_path: str | Path,
    icepak_bin: str | None,
    env_script: str | None,
    tcl_script: Path,
    extra_env: dict[str, str] | None = None,
    log: Callable[[str], None] | None = None,
    progress: Callable[[ProgressUpdate], None] | None = None,
) -> tuple[int, list[str]]:
    logger = log or print
    project_dir = resolve_icepak_project(Path(input_path))
    resolved_icepak_bin = resolve_icepak_bin(icepak_bin, env_script)
    command = build_command(resolved_icepak_bin, tcl_script, project_dir, env_script)

    logger(f"Icepak 工程：{project_dir}")
    logger(f"Icepak 可执行文件：{resolved_icepak_bin}")
    logger(f"Tcl 脚本：{tcl_script}")

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    lines: list[str] = []
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.rstrip()
        lines.append(stripped)
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
        logger(stripped)

    return process.wait(), lines


def _parse_table_output(lines: Iterable[str], default_export_name: str) -> TableData | None:
    columns: list[str] = []
    rows: list[tuple[str, ...]] = []

    for stripped in lines:
        if stripped.startswith(TABLE_COLUMNS_PREFIX):
            columns = stripped[len(TABLE_COLUMNS_PREFIX) :].split("\t")
            continue
        if stripped.startswith(TABLE_ROW_PREFIX):
            rows.append(tuple(stripped[len(TABLE_ROW_PREFIX) :].split("\t")))

    if not columns:
        return None

    return TableData(
        columns=tuple(columns),
        rows=tuple(rows),
        default_export_name=default_export_name,
    )


def list_block_dimensions(
    input_path: str | Path,
    icepak_bin: str | None = None,
    env_script: str | None = None,
    tcl_script: str | None = None,
    log: Callable[[str], None] | None = None,
    progress: Callable[[ProgressUpdate], None] | None = None,
) -> ToolExecutionResult:
    resolved_tcl_script = resolve_tcl_script(tcl_script, DEFAULT_LIST_TCL_SCRIPT)
    if progress is not None:
        progress(ProgressUpdate(mode="indeterminate", message="正在枚举 hexa block..."))
    exit_code, lines = _run_icepak_script(
        input_path=input_path,
        icepak_bin=icepak_bin,
        env_script=env_script,
        tcl_script=resolved_tcl_script,
        log=log,
        progress=progress,
    )
    table_data = _parse_table_output(lines, default_export_name="paired_block_dz_blocks.csv")
    if progress is not None:
        progress(ProgressUpdate(mode="determinate", value=99, maximum=100, message="Hexa block 枚举完成，正在整理结果..."))
    return ToolExecutionResult(exit_code=exit_code, table_data=table_data)


def parse_block_records(table_data: TableData) -> tuple[BlockRecord, ...]:
    if not table_data.rows:
        return ()

    columns = {name: index for index, name in enumerate(table_data.columns)}
    required_columns = (
        "object_name",
        "object_type",
        "shape_name",
        "shape_type",
        "length_unit",
        "dx",
        "dy",
        "dz",
        "xmin",
        "xmax",
        "ymin",
        "ymax",
        "zmin",
        "zmax",
    )
    missing = [name for name in required_columns if name not in columns]
    if missing:
        raise ValueError(f"表格缺少必要列：{', '.join(missing)}")

    records: list[BlockRecord] = []
    for row in table_data.rows:
        records.append(
            BlockRecord(
                object_name=row[columns["object_name"]],
                object_type=row[columns["object_type"]],
                shape_name=row[columns["shape_name"]],
                shape_type=row[columns["shape_type"]],
                length_unit=row[columns["length_unit"]],
                dx=float(row[columns["dx"]]),
                dy=float(row[columns["dy"]]),
                dz=float(row[columns["dz"]]),
                xmin=float(row[columns["xmin"]]),
                xmax=float(row[columns["xmax"]]),
                ymin=float(row[columns["ymin"]]),
                ymax=float(row[columns["ymax"]]),
                zmin=float(row[columns["zmin"]]),
                zmax=float(row[columns["zmax"]]),
            )
        )
    return tuple(records)


AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
THICKNESS_LABEL = {"x": "dx", "y": "dy", "z": "dz"}


def normalize_stack_axis(stack_axis: str | None) -> str:
    axis = (stack_axis or "z").strip().lower()
    if axis not in AXIS_INDEX:
        raise ValueError("厚度堆叠方向必须是 x、y 或 z。")
    return axis


def _axis_range(record: BlockRecord, axis: str) -> tuple[float, float]:
    if axis == "x":
        return record.xmin, record.xmax
    if axis == "y":
        return record.ymin, record.ymax
    return record.zmin, record.zmax


def _thickness(record: BlockRecord, axis: str) -> float:
    if axis == "x":
        return record.dx
    if axis == "y":
        return record.dy
    return record.dz


def _cross_section_matches(selected: BlockRecord, other: BlockRecord, stack_axis: str) -> bool:
    other_axes = [axis for axis in ("x", "y", "z") if axis != stack_axis]
    for axis in other_axes:
        selected_min, selected_max = _axis_range(selected, axis)
        other_min, other_max = _axis_range(other, axis)
        if not _approximately_equal(selected_min, other_min):
            return False
        if not _approximately_equal(selected_max, other_max):
            return False
    return True


def _approximately_equal(left: float, right: float, tolerance: float = EPSILON_MM) -> bool:
    return abs(left - right) <= tolerance


def build_adjustment_plan(
    records: Iterable[BlockRecord],
    selected_name: str,
    stack_axis: str,
    direction_sign: str,
    delta_mm: float,
) -> PairAdjustmentPlan:
    axis = normalize_stack_axis(stack_axis)
    if direction_sign not in {"+", "-"}:
        raise ValueError(f"不支持的方向符号：{direction_sign}")
    if abs(delta_mm) <= EPSILON_MM:
        raise ValueError("调整量不能为 0。")

    matching = [record for record in records if record.object_name == selected_name]
    if not matching:
        raise ValueError(f"未找到 block：{selected_name}")
    if len(matching) > 1:
        raise ValueError(f"存在重名 block，无法唯一定位：{selected_name}")

    selected = matching[0]
    if selected.shape_type != "hexa":
        raise ValueError(f"当前只支持 hexa block，所选 block 的 shape_type 为 {selected.shape_type}。")

    selected_min, selected_max = _axis_range(selected, axis)
    shared_coordinate = selected_max if direction_sign == "+" else selected_min
    touching: list[BlockRecord] = []
    for record in records:
        if record.object_name == selected.object_name:
            continue
        record_min, record_max = _axis_range(record, axis)
        boundary = record_min if direction_sign == "+" else record_max
        if _approximately_equal(boundary, shared_coordinate):
            touching.append(record)

    if not touching:
        raise ValueError(
            f"所选 block 在 {direction_sign.upper()}{axis.upper()} 方向没有找到相邻 block。"
        )

    matching_section = [
        record
        for record in touching
        if _cross_section_matches(selected, record, axis)
    ]

    if len(matching_section) > 1:
        matching_names = ", ".join(record.object_name for record in matching_section)
        raise ValueError(
            "所选方向存在多个相邻 block，无法确定唯一配对对象："
            f"{matching_names}。"
        )

    if len(matching_section) != 1:
        partner = touching[0]
        raise ValueError(
            "相邻 block 与所选 block 的截面范围不一致，不能执行配对厚度调整："
            f"{partner.object_name}。"
        )

    partner = matching_section[0]
    if partner.shape_type != "hexa":
        raise ValueError(f"当前只支持 hexa 配对 block，相邻 block 的 shape_type 为 {partner.shape_type}。")

    thickness_name = THICKNESS_LABEL[axis]
    selected_thickness = _thickness(selected, axis)
    partner_thickness = _thickness(partner, axis)
    new_selected_thickness = selected_thickness + delta_mm
    new_partner_thickness = partner_thickness - delta_mm
    if new_selected_thickness <= EPSILON_MM:
        raise ValueError(f"调整后所选 block 的 {thickness_name} 必须大于 0。")
    if new_partner_thickness <= EPSILON_MM:
        raise ValueError(f"调整后相邻 block 的 {thickness_name} 必须大于 0。")

    new_shared_coordinate = (
        shared_coordinate + delta_mm if direction_sign == "+" else shared_coordinate - delta_mm
    )
    return PairAdjustmentPlan(
        selected=selected,
        partner=partner,
        stack_axis=axis,
        direction_sign=direction_sign,
        delta_mm=delta_mm,
        new_shared_coordinate=new_shared_coordinate,
        new_selected_thickness=new_selected_thickness,
        new_partner_thickness=new_partner_thickness,
    )


def apply_pair_adjustment(
    *,
    parameters: dict[str, str],
    plan: PairAdjustmentPlan,
    log: Callable[[str], None] | None = None,
) -> None:
    resolved_tcl_script = resolve_tcl_script(None, DEFAULT_ADJUST_TCL_SCRIPT)
    exit_code, lines = _run_icepak_script(
        input_path=parameters["input_path"],
        icepak_bin=parameters.get("icepak_bin") or None,
        env_script=parameters.get("env_script") or None,
        tcl_script=resolved_tcl_script,
        extra_env={
            "QD_SELECTED_BLOCK": plan.selected.object_name,
            "QD_PARTNER_BLOCK": plan.partner.object_name,
            "QD_STACK_AXIS": plan.stack_axis,
            "QD_DIRECTION_SIGN": plan.direction_sign,
            "QD_DELTA_M": str(plan.delta_mm / 1000.0),
        },
        log=log,
    )
    if exit_code != 0:
        relevant_lines = [line for line in lines if line]
        detail = "\n".join(relevant_lines[-12:]) if relevant_lines else f"退出码 {exit_code}"
        raise RuntimeError(f"配对厚度调整失败。\n{detail}")