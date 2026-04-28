from __future__ import annotations

import json
from dataclasses import dataclass, field


MATCH_MODE_CHOICES = (
    ("块名精确匹配", "exact"),
    ("块名通配匹配", "wildcard"),
    ("块名正则匹配", "regex"),
)

OBJECT_OVERRIDE_KEY_MAP = {
    "grid_size_x": "size_x",
    "grid_size_y": "size_y",
    "grid_size_z": "size_z",
    "grid_sep_x": "sep_x",
    "grid_sep_y": "sep_y",
    "grid_sep_z": "sep_z",
    "grid_enable_prism_layer": "enable_prism_layer",
    "grid_tetra_smqual": "tetra_smqual",
    "grid_tetra_smiters": "tetra_smiters",
    "grid_hdm_refine_features": "hdm_refine_features",
    "grid_include_all_gaps": "include_all_gaps",
}
OBJECT_OVERRIDE_KEY_TO_PARAMETER_KEY = {
    object_key: parameter_key for parameter_key, object_key in OBJECT_OVERRIDE_KEY_MAP.items()
}


@dataclass(frozen=True)
class RuleFieldSpec:
    key: str
    label: str
    value_type: str
    minimum: float | None = None
    maximum: float | None = None


RULE_OVERRIDE_FIELD_SPECS = (
    RuleFieldSpec("grid_size_x", "局部尺寸 X", "float", 0.0),
    RuleFieldSpec("grid_size_y", "局部尺寸 Y", "float", 0.0),
    RuleFieldSpec("grid_size_z", "局部尺寸 Z", "float", 0.0),
    RuleFieldSpec("grid_sep_x", "局部分离间隙 X", "float", 0.0),
    RuleFieldSpec("grid_sep_y", "局部分离间隙 Y", "float", 0.0),
    RuleFieldSpec("grid_sep_z", "局部分离间隙 Z", "float", 0.0),
    RuleFieldSpec("grid_tetra_smqual", "局部平滑质量阈值", "float", 0.0, 1.0),
    RuleFieldSpec("grid_tetra_smiters", "局部平滑迭代次数", "integer", 1),
    RuleFieldSpec("grid_enable_prism_layer", "局部棱柱层", "boolean"),
    RuleFieldSpec("grid_hdm_refine_features", "局部特征细化", "boolean"),
    RuleFieldSpec("grid_include_all_gaps", "局部全部窄缝包含", "boolean"),
)
RULE_OVERRIDE_FIELD_MAP = {field.key: field for field in RULE_OVERRIDE_FIELD_SPECS}


@dataclass
class MeshRefinementRule:
    name: str
    enabled: bool = True
    priority: int = 100
    match_mode: str = "wildcard"
    patterns: list[str] = field(default_factory=list)
    overrides: dict[str, str] = field(default_factory=dict)


def _normalize_boolean(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"

    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return "1"
    if normalized in {"0", "false", "no", "off"}:
        return "0"
    raise ValueError(f"无效的布尔值：{value}")


def _normalize_patterns(value: object) -> list[str]:
    if isinstance(value, str):
        raw_patterns = value.replace(",", "\n").splitlines()
    elif isinstance(value, (list, tuple)):
        raw_patterns = value
    else:
        raise ValueError("匹配模式必须是字符串列表")

    patterns = [str(item).strip() for item in raw_patterns if str(item).strip()]
    return patterns


def _normalize_override_value(field_spec: RuleFieldSpec, value: object) -> str:
    normalized = str(value).strip()
    if not normalized:
        return ""

    if field_spec.value_type == "boolean":
        return _normalize_boolean(normalized)

    if field_spec.value_type == "integer":
        integer_value = int(float(normalized))
        if field_spec.minimum is not None and integer_value < field_spec.minimum:
            raise ValueError(f"{field_spec.label} 不能小于 {field_spec.minimum}")
        if field_spec.maximum is not None and integer_value > field_spec.maximum:
            raise ValueError(f"{field_spec.label} 不能大于 {field_spec.maximum}")
        return str(integer_value)

    if field_spec.value_type == "float":
        float_value = float(normalized)
        if field_spec.minimum is not None and float_value < field_spec.minimum:
            raise ValueError(f"{field_spec.label} 不能小于 {field_spec.minimum}")
        if field_spec.maximum is not None and float_value > field_spec.maximum:
            raise ValueError(f"{field_spec.label} 不能大于 {field_spec.maximum}")
        return normalized

    return normalized


def normalize_mesh_refinement_rule(rule: MeshRefinementRule | dict[str, object], index: int) -> MeshRefinementRule:
    candidate = rule if isinstance(rule, dict) else {
        "name": rule.name,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "match_mode": rule.match_mode,
        "patterns": rule.patterns,
        "overrides": rule.overrides,
    }

    name = str(candidate.get("name", "")).strip()
    if not name:
        raise ValueError(f"第 {index + 1} 条规则缺少名称")

    match_mode = str(candidate.get("match_mode", "wildcard")).strip() or "wildcard"
    allowed_modes = {value for _label, value in MATCH_MODE_CHOICES}
    if match_mode not in allowed_modes:
        raise ValueError(f"规则 {name} 的匹配模式不受支持：{match_mode}")

    patterns = _normalize_patterns(candidate.get("patterns", []))
    if not patterns:
        raise ValueError(f"规则 {name} 至少需要一个块名匹配模式")

    raw_overrides = candidate.get("overrides", {})
    if not isinstance(raw_overrides, dict):
        raise ValueError(f"规则 {name} 的覆盖项必须是字典")

    overrides: dict[str, str] = {}
    for key, raw_value in raw_overrides.items():
        field_spec = RULE_OVERRIDE_FIELD_MAP.get(str(key))
        if field_spec is None:
            raise ValueError(f"规则 {name} 包含未知覆盖项：{key}")
        value = _normalize_override_value(field_spec, raw_value)
        if value:
            overrides[field_spec.key] = value

    if not overrides:
        raise ValueError(f"规则 {name} 至少需要一个局部覆盖项")

    return MeshRefinementRule(
        name=name,
        enabled=bool(candidate.get("enabled", True)),
        priority=int(candidate.get("priority", 100)),
        match_mode=match_mode,
        patterns=patterns,
        overrides=overrides,
    )


def deserialize_mesh_refinement_rules(serialized: str | None) -> list[MeshRefinementRule]:
    if not serialized or not serialized.strip():
        return []

    try:
        payload = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError(f"块组细化规则格式错误：{exc.msg}") from exc

    if not isinstance(payload, list):
        raise ValueError("块组细化规则必须是规则列表")

    return [normalize_mesh_refinement_rule(item, index) for index, item in enumerate(payload)]


def serialize_mesh_refinement_rules(rules: list[MeshRefinementRule] | tuple[MeshRefinementRule, ...]) -> str:
    normalized_rules = [normalize_mesh_refinement_rule(rule, index) for index, rule in enumerate(rules)]
    payload = [
        {
            "name": rule.name,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "match_mode": rule.match_mode,
            "patterns": rule.patterns,
            "overrides": rule.overrides,
        }
        for rule in normalized_rules
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def summarize_mesh_refinement_rules(serialized: str | None) -> str:
    try:
        rules = deserialize_mesh_refinement_rules(serialized)
    except ValueError:
        return "规则格式无效，点击编辑修复"

    if not rules:
        return "未配置块组细化规则"

    enabled_count = sum(1 for rule in rules if rule.enabled)
    override_count = sum(len(rule.overrides) for rule in rules)
    return f"共 {len(rules)} 条规则，启用 {enabled_count} 条，覆盖项 {override_count} 个"


def _tcl_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
    return f'"{escaped}"'


def _tcl_list(values: list[str]) -> str:
    if not values:
        return "[list]"
    return "[list {}]".format(" ".join(_tcl_string(value) for value in values))


def build_mesh_rules_tcl(rules: list[MeshRefinementRule] | tuple[MeshRefinementRule, ...]) -> str:
    normalized_rules = sorted(
        (normalize_mesh_refinement_rule(rule, index) for index, rule in enumerate(rules) if bool((rule.enabled if isinstance(rule, MeshRefinementRule) else rule.get("enabled", True)))),
        key=lambda item: (item.priority, item.name.casefold()),
    )

    if not normalized_rules:
        return "set quard_mesh_refinement_rules [list]\n"

    lines = ["set quard_mesh_refinement_rules [list \\"]
    for rule in normalized_rules:
        override_parts: list[str] = []
        for key, value in sorted(rule.overrides.items()):
            override_parts.append(_tcl_string(key))
            override_parts.append(_tcl_string(value))
        override_literal = "[dict create {}]".format(" ".join(override_parts)) if override_parts else "[dict create]"
        lines.extend(
            [
                "    [dict create \\",
                f"        enabled 1 \\",
                f"        name {_tcl_string(rule.name)} \\",
                f"        priority {rule.priority} \\",
                f"        match_mode {_tcl_string(rule.match_mode)} \\",
                f"        patterns {_tcl_list(rule.patterns)} \\",
                f"        overrides {override_literal} \\",
                "    ] \\",
            ]
        )
    lines.append("]")
    lines.append("")
    return "\n".join(lines)