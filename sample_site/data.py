"""Offline demo data for the paginated sample newspaper site."""

from __future__ import annotations

ISSUES: dict[str, dict] = {
    "clean": {
        "slug": "clean",
        "issue": "2024-05-01",
        "edition": "第3版",
        "total_pages": 6,
        "title": "示例 A · 完整期",
        "description": "6 个页面全部由期版一致且带图片的扫描唯一覆盖。",
        "expected": "合格",
        "scans": [
            {"id": "a1", "pages": "1", "image": True},
            {"id": "a2", "pages": "2-3", "image": True},
            {"id": "a3", "pages": "4", "image": True},
            {"id": "a4", "pages": "5", "image": True},
            {"id": "a5", "pages": "6", "image": True},
        ],
    },
    "conflict": {
        "slug": "conflict",
        "issue": "2024-05-02",
        "edition": "第3版",
        "total_pages": 8,
        "title": "示例 B · 重扫与缺页",
        "description": "第 3 页被两个不同详情重复覆盖；旧链接 b3-old 与 b3 指向同一详情，不应再加一处冲突。",
        "expected": "不合格",
        "scans": [
            {"id": "b1", "pages": "1", "image": True},
            {"id": "b2", "pages": "2-3", "image": True},
            {"id": "b3", "pages": "3", "image": True, "entries": ["b3", "b3-old"]},
            {"id": "b4", "pages": "4", "image": True, "issue": "2023-12-31"},
            {"id": "b5", "pages": "5", "image": False},
            {"id": "b6", "pages": "6-7", "image": True},
            {"id": "b7", "pages": "8", "image": True},
        ],
    },
    "pending": {
        "slug": "pending",
        "issue": "2024-05-03",
        "edition": "第3版",
        "total_pages": 12,
        "title": "示例 C · 详情抓取失败",
        "description": "一个详情页返回 404；另有跨页重复覆盖、版次不符和缺页，整期只能待核实。",
        "expected": "待核实",
        "scans": [
            {"id": "c1", "pages": "1", "image": True},
            {"id": "c2", "pages": "2-3", "image": True},
            {"id": "c3", "pages": "4", "image": True},
            {"id": "c4", "pages": "4", "image": True},
            {"id": "c5", "pages": "5", "image": True, "broken": True},
            {"id": "c6", "pages": "6-7", "image": True},
            {"id": "c7", "pages": "8", "image": True},
            {"id": "c8", "pages": "9", "image": True, "edition": "第4版"},
            {"id": "c9", "pages": "10", "image": True},
        ],
    },
    "redirect": {
        "slug": "redirect",
        "issue": "2024-05-04",
        "edition": "第3版",
        "total_pages": 6,
        "title": "示例 D · 旧链接归并",
        "description": "旧链接经站内重定向指向新详情，且两个入口跨目录分页出现；归并后每页仍只有一个扫描。",
        "expected": "合格",
        "scans": [
            {"id": "d1", "pages": "1", "image": True, "entries": ["d1", "d1-old"]},
            {"id": "d2", "pages": "2-3", "image": True, "entries": ["d2", "d2-old"]},
            {"id": "d3", "pages": "4", "image": True},
            {"id": "d4", "pages": "5", "image": True},
            {"id": "d5", "pages": "6", "image": True},
        ],
    },
    "alias-failure": {
        "slug": "alias-failure",
        "issue": "2024-05-06",
        "edition": "第3版",
        "total_pages": 4,
        "title": "示例 E · 一条入口失败",
        "description": "第 2 页的新入口可读，但同一条记录遗留的旧入口返回 404；即使页面均被覆盖也须整期待核实。",
        "expected": "待核实",
        "scans": [
            {"id": "f1", "pages": "1", "image": True},
            {
                "id": "f2",
                "pages": "2",
                "image": True,
                "entries": ["f2", "f2-lost"],
                "broken_entries": ["f2-lost"],
            },
            {"id": "f3", "pages": "3", "image": True, "entries": ["f3", "f3-old"]},
            {"id": "f4", "pages": "4", "image": True},
        ],
    },
}

ISSUE_ORDER = ["clean", "conflict", "pending", "redirect", "alias-failure"]
PAGE_SIZE = 3


def get_issue(slug: str) -> dict | None:
    return ISSUES.get(slug)


def scan_issue(scan: dict, issue: dict) -> str:
    return scan.get("issue", issue["issue"])


def scan_edition(scan: dict, issue: dict) -> str:
    return scan.get("edition", issue["edition"])


def scan_image_path(slug: str, scan: dict) -> str:
    return f"/img/{slug}-{scan['id']}.svg"


def scan_entries(scan: dict) -> list[str]:
    """Directory entry ids for one scan; legacy ids redirect to ``scan['id']``."""
    return list(scan.get("entries", [scan["id"]]))


def scan_broken_entries(scan: dict) -> set[str]:
    return set(scan.get("broken_entries", []))


def find_entry(issue: dict, entry_id: str) -> tuple[dict | None, bool]:
    """Return (scan, is_legacy_entry) for a directory entry id."""
    for scan in issue["scans"]:
        if scan["id"] == entry_id:
            return scan, False
        if entry_id in scan.get("entries", []):
            return scan, True
    return None, False
