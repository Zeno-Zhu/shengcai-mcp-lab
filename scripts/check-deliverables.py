#!/usr/bin/env python3
"""shengcai-mcp-lab 交付物 L1 机械校验。

只判断能由文件和格式确定的事实；语义与质量判断保留给 L2 / L3。

    python scripts/check-deliverables.py --task-dir <任务目录>

脚本必须接收显式 --task-dir，没有默认路径，也不写入 Skill 目录。
校验结果可用 --evidence-out 写入任务目录，例如 <task-dir>/validation.md。
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

CARD_SIZE = (1080, 1350)
CARD_MIN, CARD_MAX = 1, 5

SOURCE_LABELS = (
    "风向标", "精华帖", "中标帖", "日常帖", "朋友圈", "项目库",
    "航海", "深海圈", "课程", "评论", "问答", "足迹",
)
NEXT_STEP_RE = re.compile(r"下一步|今晚|本周|下周|动作|验证|实验")
BOUNDARY_RE = re.compile(r"未知|边界|风险|限制|未提供|不构成|不代表|不说明|暂时不能")
HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
# 外部依赖：link/script/img/iframe 指向网络或站外资源，则不再是单文件自包含。
EXTERNAL_HTML_RE = re.compile(
    r"""<(?:link|script|img|iframe)\b[^>]*\b(?:src|href)\s*=\s*["']?(?:https?:)?//""",
    re.IGNORECASE,
)
HTTP_RE = re.compile(r"https?://")


def png_size(path: Path):
    """读取 PNG IHDR，返回 (宽, 高)；不是合法 PNG 时返回 None。"""
    with path.open("rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def find_skill_root(task_dir: Path):
    """若任务目录位于某个 Skill 包内，返回该 Skill 根目录。"""
    for candidate in (task_dir, *task_dir.parents):
        if (candidate / "SKILL.md").is_file():
            return candidate
    return None


def check(task_dir: Path):
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    if not task_dir.is_dir():
        return [f"任务目录不存在：{task_dir}"], warnings, notes

    skill_root = find_skill_root(task_dir)
    if skill_root == task_dir:
        errors.append("任务目录不能是 Skill 目录本身，交付物必须写在目标项目的新任务目录中。")
    elif skill_root is not None:
        errors.append(
            f"任务目录位于 Skill 包内（{skill_root}）。"
            "任务产物不得写入 Skill 目录，请改到目标项目的新任务目录。"
        )

    report = task_dir / "report.md"
    if not report.is_file():
        errors.append("缺少母稿 report.md。")
    else:
        text = report.read_text(encoding="utf-8", errors="replace")
        if len(HEADING_RE.findall(text)) < 2:
            errors.append("report.md 结构不足：至少需要判断与结论两个层级的小标题。")
        if not NEXT_STEP_RE.search(text):
            errors.append("report.md 未写明下一步动作（下一步／本周／验证／实验）。")
        if not BOUNDARY_RE.search(text):
            errors.append("report.md 未写明边界或未知项（未知／边界／风险／限制）。")
        labels = {label for label in SOURCE_LABELS if label in text}
        if len(labels) < 2:
            warnings.append(
                "report.md 未识别到两个以上来源标签（风向标／精华帖／航海／深海圈等），"
                "报告可能把不同来源混成同一种推荐。"
            )
        if not HTTP_RE.search(text):
            warnings.append("report.md 未发现可回查的原帖链接。")

    if not (task_dir / "direction-card.md").is_file():
        warnings.append("任务目录缺少 direction-card.md（最小方向卡）。")

    for html in sorted(task_dir.glob("*.html")):
        html_text = html.read_text(encoding="utf-8", errors="replace")
        if EXTERNAL_HTML_RE.search(html_text):
            errors.append(f"{html.name} 依赖站外资源，不是单文件自包含 HTML。")
        notes.append(f"已检查单文件 HTML：{html.name}")

    cards = sorted((task_dir / "cards").glob("card-*.png"))
    if cards:
        if not CARD_MIN <= len(cards) <= CARD_MAX:
            errors.append(f"卡片数量为 {len(cards)}，超出 {CARD_MIN}–{CARD_MAX} 张的范围。")
        elif len(cards) == 2:
            warnings.append("仅有 2 张卡片：单条强信号用 1 张，多篇阅读应为 3–5 张。")
        for card in cards:
            size = png_size(card)
            if size is None:
                errors.append(f"{card.name} 不是合法 PNG。")
            elif size != CARD_SIZE:
                errors.append(
                    f"{card.name} 尺寸为 {size[0]}×{size[1]}，应为 {CARD_SIZE[0]}×{CARD_SIZE[1]}。"
                )
        notes.append(f"已检查 {len(cards)} 张朋友圈卡尺寸。")
    else:
        notes.append("未发现 cards/card-*.png（本次可能只交付母稿或网页）。")

    cards_html = task_dir / "cards.html"
    if cards_html.is_file() and HTTP_RE.search(cards_html.read_text(encoding="utf-8", errors="replace")):
        warnings.append("cards.html 出现链接：公开卡不应展示圈友名、原帖链接或来源脚注。")

    return errors, warnings, notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="shengcai-mcp-lab 交付物 L1 机械校验（母稿、来源分区、卡片尺寸、HTML 自包含、工作区隔离）。"
    )
    parser.add_argument("--task-dir", type=Path, required=True, help="目标项目中的任务目录（显式传入）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出，便于脚本消费")
    parser.add_argument("--evidence-out", type=Path, default=None, help="把校验结果写入该路径（不默认写入任何位置）")
    args = parser.parse_args()

    task_dir = args.task_dir.expanduser().resolve()
    errors, warnings, notes = check(task_dir)
    status = "FAIL" if errors else "PASS"

    if args.json:
        payload = {
            "task_dir": str(task_dir),
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "notes": notes,
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        lines = [f"{status}: {task_dir}"]
        lines += [f"ERROR: {item}" for item in errors]
        lines += [f"WARN: {item}" for item in warnings]
        lines += [f"NOTE: {item}" for item in notes]
        rendered = "\n".join(lines)

    if args.evidence_out is not None:
        args.evidence_out.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")

    print(rendered)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
