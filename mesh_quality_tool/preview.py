from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from icepak_runtime import build_command, resolve_icepak_bin, resolve_icepak_project

from .rules import build_mesh_rules_tcl, deserialize_mesh_refinement_rules


DEFAULT_PREVIEW_TCL_SCRIPT = Path(__file__).resolve().with_name("preview_mesh_refinement_rules.tcl")
PREVIEW_RULE_PREFIX = "__QD_PREVIEW_RULE__\t"
PREVIEW_MATCH_PREFIX = "__QD_PREVIEW_MATCH__\t"
MESH_RULES_ENV_KEY = "QUARD_ICEPAK_MESH_RULES_FILE"


@dataclass(frozen=True)
class MeshRulePreviewMatch:
    rule_name: str
    object_name: str


@dataclass(frozen=True)
class MeshRulePreviewSummary:
    rule_name: str
    priority: int
    match_mode: str
    patterns: tuple[str, ...]
    matched_count: int


@dataclass(frozen=True)
class MeshRulePreviewResult:
    summaries: tuple[MeshRulePreviewSummary, ...]
    matches: tuple[MeshRulePreviewMatch, ...]

    @property
    def total_matches(self) -> int:
        return len(self.matches)


def _split_encoded_list(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item for item in value.split("|") if item)


def _parse_preview_rule(parts: list[str]) -> MeshRulePreviewSummary | None:
    if len(parts) < 5:
        return None
    try:
        priority = int(parts[1])
        matched_count = int(parts[4])
    except ValueError:
        return None
    return MeshRulePreviewSummary(
        rule_name=parts[0],
        priority=priority,
        match_mode=parts[2],
        patterns=_split_encoded_list(parts[3]),
        matched_count=matched_count,
    )


def preview_mesh_refinement_rules(
    input_path: str,
    serialized_rules: str,
    env_script: str | None = None,
    icepak_bin: str | None = None,
) -> MeshRulePreviewResult:
    rules = deserialize_mesh_refinement_rules(serialized_rules)
    if not rules:
        raise ValueError("请先至少配置一条有效规则，再进行预览。")

    preview_script = DEFAULT_PREVIEW_TCL_SCRIPT
    if not preview_script.exists():
        raise FileNotFoundError(f"预览脚本不存在：{preview_script}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".tcl",
        prefix="quard_mesh_rules_preview_",
        delete=False,
        encoding="utf-8",
        newline="\n",
    ) as handle:
        rules_file = Path(handle.name)
        handle.write(build_mesh_rules_tcl(rules))

    process_env = None
    try:
        process_env = {MESH_RULES_ENV_KEY: str(rules_file)}
        project_dir = resolve_icepak_project(Path(input_path))
        resolved_icepak_bin = resolve_icepak_bin(icepak_bin, env_script)
        command = build_command(resolved_icepak_bin, preview_script, project_dir, env_script)
        env = None
        if process_env:
            env = dict(**process_env)
            import os

            merged_env = os.environ.copy()
            merged_env.update(process_env)
            env = merged_env

        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            env=env,
        )
    finally:
        try:
            rules_file.unlink()
        except OSError:
            pass

    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or "规则预览执行失败。")

    summaries: list[MeshRulePreviewSummary] = []
    matches: list[MeshRulePreviewMatch] = []
    for raw_line in completed.stdout.splitlines():
        stripped = raw_line.rstrip()
        if stripped.startswith(PREVIEW_RULE_PREFIX):
            summary = _parse_preview_rule(stripped[len(PREVIEW_RULE_PREFIX) :].split("\t"))
            if summary is not None:
                summaries.append(summary)
            continue
        if stripped.startswith(PREVIEW_MATCH_PREFIX):
            parts = stripped[len(PREVIEW_MATCH_PREFIX) :].split("\t")
            if len(parts) >= 2:
                matches.append(MeshRulePreviewMatch(rule_name=parts[0], object_name=parts[1]))

    return MeshRulePreviewResult(summaries=tuple(summaries), matches=tuple(matches))