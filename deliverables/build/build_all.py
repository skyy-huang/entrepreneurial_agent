# -*- coding: utf-8 -*-
"""
交付物构建脚本：Markdown → DOCX → PDF

流程：
  1. 读取 deliverables/src/*.md
  2. 把附录A、附录B 并入《03_创新性项目开发文档》（它们在文档内被索引）
  3. 转换为 deliverables/build/docx/*.docx
  4. 调用 Word COM 批量导出 deliverables/*.pdf

用法：python deliverables/build/build_all.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(_ROOT, "deliverables", "src")
DOCX_DIR = os.path.join(_ROOT, "deliverables", "build", "docx")
OUT = os.path.join(_ROOT, "deliverables")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_to_docx import convert  # noqa: E402

# 交付物编号 → 源文件（不含扩展名）
DELIVERABLES = [
    ("03_创新性项目开发文档", ["03_创新性项目开发文档", "附录A_证据与假设台账", "附录B_候选选题决策矩阵"]),
    ("04_智能体迭代开发文档", ["04_智能体迭代开发文档"]),
    ("05_创新性说明", ["05_创新性说明"]),
    ("06_自测试报告", ["06_自测试报告"]),
    ("07_用户手册", ["07_用户手册"]),
    ("08_小组总结", ["08_小组总结"]),
]


def read(name: str) -> str:
    with open(os.path.join(SRC, f"{name}.md"), "r", encoding="utf-8") as f:
        return f.read()


def merge(sources: list[str]) -> str:
    """把多个 Markdown 源合并成一篇。

    附录标题降一级，避免与正文的 H1 冲突；附录从新的一页开始。
    """
    parts = [read(sources[0])]
    for extra in sources[1:]:
        body = read(extra)
        # 附录文件自身的 H1 降为 H2
        body = re.sub(r"^#\s+", "## ", body, count=1, flags=re.M)
        parts.append("\n\n---\n\n" + body)
    return "\n\n".join(parts)


def main() -> int:
    os.makedirs(DOCX_DIR, exist_ok=True)
    # 合并后的临时 markdown 也存一份，便于人工核对转换前的最终内容
    merged_dir = os.path.join(_ROOT, "deliverables", "build", "merged")
    os.makedirs(merged_dir, exist_ok=True)

    pairs: list[tuple[str, str]] = []
    for out_name, sources in DELIVERABLES:
        md = merge(sources)
        md_path = os.path.join(merged_dir, f"{out_name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        docx_path = os.path.join(DOCX_DIR, f"{out_name}.docx")
        convert(md_path, docx_path)
        pairs.append((docx_path, os.path.join(OUT, f"{out_name}.pdf")))
        print(f"[DOCX] {out_name}.docx")

    # 个人总结：每份单独成篇，输出到 09_个人总结/
    personal_src = os.path.join(OUT, "09_个人总结")
    if os.path.isdir(personal_src):
        for name in sorted(os.listdir(personal_src)):
            if not name.endswith(".md"):
                continue
            stem = name[:-3]
            md_path = os.path.join(personal_src, name)
            docx_path = os.path.join(DOCX_DIR, "09", f"{stem}.docx")
            convert(md_path, docx_path)
            pairs.append((docx_path, os.path.join(personal_src, f"{stem}.pdf")))
            print(f"[DOCX] 09_个人总结/{stem}.docx")

    # ── Word COM 批量导出 PDF ──────────────────────────────────
    # 用 -Command 传内联脚本，不写 .ps1、也不动 ExecutionPolicy。
    script_lines = [
        "$ErrorActionPreference='Stop'",
        "$w = New-Object -ComObject Word.Application",
        "$w.Visible=$false",
    ]
    for docx, pdf in pairs:
        script_lines.append(
            f"$d = $w.Documents.Open('{docx}', $false, $true); "
            f"$d.ExportAsFixedFormat('{pdf}', 17); $d.Close($false)"
        )
        script_lines.append(f"Write-Output 'PDF {os.path.basename(pdf)}'")
    script_lines.append("$w.Quit()")

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "; ".join(script_lines)],
        capture_output=True, text=True, timeout=600,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print("PDF 导出失败：", result.stderr.strip()[:800], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
