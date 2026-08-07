"""Config loading + ``${path.to.key}`` template expansion.

Pure module (stdlib only) so it is unit-testable on any machine — the
launcher runs on Windows but is developed on macOS.

Design (§5 of docs/O2_LAUNCHER.md): the operator is non-IT and the
programmer cannot see the real Windows/WSL2 environment, so every
environment-specific value lives in ``config.json`` as a placeholder /
sensible default.  Strings may reference other config values with
``${section.key}``, e.g. ``${sync.dst_root}\\gtec_bridge`` — this keeps
paths derived from one root instead of duplicated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Top-level sections config.json must provide.
REQUIRED_SECTIONS = ("service", "wsl", "sync", "web", "devices", "sidebar")

_TEMPLATE_RE = re.compile(r"\$\{([a-z0-9_.]+)\}", re.IGNORECASE)


def _resolve_ref(ref: str, cfg: dict) -> Any:
    """Resolve ``'a.b.c'`` against *cfg*; KeyError with a clear message if missing."""
    node: Any = cfg
    for part in ref.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise ValueError(f"config.json 引用了不存在的字段: ${{{ref}}} (缺 {part!r})")
    return node


def expand_config(cfg: dict) -> dict:
    """Recursively expand ``${path.to.key}`` placeholders inside strings.

    References resolve against the same config dict, so a value may depend
    on another (e.g. a device cwd derived from ``sync.dst_root``).  A
    missing reference raises instead of silently producing a broken path.
    """
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            return _TEMPLATE_RE.sub(lambda m: _resolve_ref(m.group(1), cfg), node)
        return node

    return walk(cfg)


def load_config(path: str | Path) -> dict:
    """Load, validate and expand ``config.json``.

    Raises
    ------
    ValueError
        File missing / invalid JSON / missing required sections / bad
        template reference — all with a Chinese, non-IT-friendly message.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"配置文件不存在: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json 解析失败(JSON 语法错误): {exc}")

    if not isinstance(raw, dict):
        raise ValueError("config.json 顶层必须是对象 (键值对)")

    missing = [s for s in REQUIRED_SECTIONS if s not in raw]
    if missing:
        raise ValueError(f"config.json 缺少必需字段: {', '.join(missing)}")

    return expand_config(raw)
