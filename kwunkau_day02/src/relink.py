"""推送 Notebook 后的第二段：校验锁定链接 → 回填 README/需求.md → 重新生成报告与一页图解。

锁定链接依赖 Notebook 的提交号，必须在 Notebook 提交并推送之后才能生成，
因此不能并入 run_all.py 的同一次运行。
"""

from __future__ import annotations

import re

from .config import (GITHUB_REPO, GITHUB_USER, NB_COMMIT, NBVIEWER_URL, ROOT,
                     nb_link_problem)

# 文档里出现的锁定链接：只替换提交号部分
_PINNED = re.compile(
    rf"(rawcdn\.githack\.com/{GITHUB_USER}/{GITHUB_REPO}/)[0-9a-f]{{7,40}}(/)")
LINK_DOCS = [ROOT / "README.md", ROOT / "需求" / "需求.md"]


def check() -> None:
    """锁定链接与本地 Notebook 不一致时直接报错，禁止生成带过期链接的 PDF。"""
    problem = nb_link_problem()
    if problem:
        raise SystemExit(
            f"[relink] {problem}。\n"
            "         请先提交并推送 Notebook（git add output/*_research.ipynb && "
            "git commit && git push），再运行：python run_all.py --relink")


def sync_docs() -> list[str]:
    """把 README / 需求.md 中的锁定链接改到当前提交号，返回被改动的文件名。"""
    changed = []
    for path in LINK_DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new = _PINNED.sub(rf"\g<1>{NB_COMMIT}\g<2>", text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path.name)
    return changed


def run() -> str:
    check()
    from .make_explainer import build as build_explainer
    from .make_report import build as build_report

    changed = sync_docs()
    build_report()
    build_explainer()
    print(f"[relink] 链接已锁定到 {NB_COMMIT[:7]}，已更新："
          f"{', '.join(changed) or '文档无需改动'}、报告、一页图解")
    return NBVIEWER_URL
