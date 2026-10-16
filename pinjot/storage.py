# -*- coding: utf-8 -*-
"""数据持久化：JSON 读写 + 原子替换 + 滚动备份 + 数据结构与迁移。

数据结构 v2（知识库树）：
  data["books"] = [
      {"id", "name", "expanded",
       "notes": [ {"id", "title", "content", "rich", "updated",
                   "expanded", "children": [...]}, ... ]}, ... ]
  data["active_book"] / data["active_note"]  当前定位
  rich = [[start, end, style], ...]          行内样式（颜色/字号/粗斜线等），
                                             start/end 为字符偏移量
v1 的扁平 notes 会自动迁移进一个默认知识库。
"""

import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from .config import APP_NAME, DEFAULT_HOTKEYS, DEF_W, DEF_H, WELCOME


LEGACY_APP_DIRS = ("PinNote",)   # 旧版本的数据目录，首次启动自动迁移
DATA_VERSION = 2


def _data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = Path(base) / APP_NAME
    if not (p / "data.json").exists():
        for legacy in LEGACY_APP_DIRS:
            old = Path(base) / legacy
            if (old / "data.json").exists():
                try:
                    shutil.copytree(old, p, dirs_exist_ok=True)
                except Exception:
                    pass
                break
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        p = Path.cwd()
    return p


DATA_FILE = _data_dir() / "data.json"


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def new_note(title="", content="") -> dict:
    """新建一篇空笔记（树节点）"""
    return {"id": new_id(), "title": title, "content": content, "rich": [],
            "updated": stamp(), "expanded": True, "children": []}


def new_book(name) -> dict:
    """新建一个知识库"""
    return {"id": new_id(), "name": name, "expanded": True, "notes": []}


def default_data() -> dict:
    book = new_book("我的笔记")
    note = new_note("欢迎使用", WELCOME)
    book["notes"].append(note)
    return {
        "version": DATA_VERSION,
        "books": [book],
        "active_book": book["id"],
        "active_note": note["id"],
        "tasks": [
            {"id": new_id(), "text": "把 PinJot 钉在屏幕角落",
             "done": True, "created": stamp()},
            {"id": new_id(), "text": "写下今天要做的三件事",
             "done": False, "created": stamp()},
        ],
        "ui": {
            "x": None, "y": None, "w": DEF_W, "h": DEF_H,
            "topmost": True, "tab": "note",
            "opacity": 1.0, "font_size": 10, "theme": "paper",
            "hotkeys": dict(DEFAULT_HOTKEYS),
        },
    }


# --------------------------------------------------------------------------- #
# 树操作工具
# --------------------------------------------------------------------------- #
def iter_notes(books):
    """深度优先遍历全部笔记：yield (book, note, siblings, parent)"""
    for book in books:
        yield from _walk(book, book["notes"], None)


def _walk(book, nodes, parent):
    for n in nodes:
        yield book, n, nodes, parent
        if n.get("children"):
            yield from _walk(book, n["children"], n)


def find_note(books, nid):
    """按 id 找笔记：返回 (book, note, siblings, parent) 或 None"""
    for book in books:
        found = _find_in_list(book, book["notes"], nid, None)
        if found:
            return found
    return None


def _find_in_list(book, nodes, nid, parent):
    for n in nodes:
        if n.get("id") == nid:
            return book, n, nodes, parent
        if n.get("children"):
            hit = _find_in_list(book, n["children"], nid, n)
            if hit:
                return hit
    return None


def find_book(books, bid):
    for b in books:
        if b.get("id") == bid:
            return b
    return None


def count_notes(books):
    """笔记总数（含所有层级）"""
    total = 0
    for book in books:
        total += _count_nodes(book["notes"])
    return total


def count_book_notes(book):
    """单个知识库的笔记数（含所有层级）"""
    return _count_nodes(book["notes"])


def _count_nodes(nodes):
    n = len(nodes)
    for x in nodes:
        n += _count_nodes(x.get("children") or [])
    return n


def first_note_id(books):
    """全树第一篇笔记的 id（用于兜底定位），没有则 None"""
    for book in books:
        if book["notes"]:
            return book["notes"][0]["id"]
    return None


# --------------------------------------------------------------------------- #
# 读写与迁移
# --------------------------------------------------------------------------- #
def _migrate(raw):
    """把旧版数据升级到 v2；已经是 v2 则原样返回。"""
    if isinstance(raw.get("books"), list) and raw["books"]:
        raw["version"] = DATA_VERSION
        for b in raw["books"]:
            b.setdefault("id", new_id())
            b.setdefault("name", "未命名")
            b.setdefault("expanded", True)
            b.setdefault("notes", [])
            _fix_nodes(b["notes"])
        return raw

    # v1：扁平 notes → 默认知识库
    notes = []
    for n in (raw.get("notes") or []):
        notes.append({
            "id": n.get("id") or new_id(),
            "title": n.get("title", ""),
            "content": n.get("content", ""),
            "rich": n.get("rich") or [],
            "updated": n.get("updated", stamp()),
            "expanded": True,
            "children": [],
        })
    if not notes:
        notes = [new_note("欢迎使用", WELCOME)]
    book = new_book("我的笔记")
    book["notes"] = notes
    raw["books"] = [book]
    raw["active_book"] = book["id"]
    if raw.get("active_note") not in [x["id"] for x in notes]:
        raw["active_note"] = notes[0]["id"]
    raw.pop("notes", None)
    raw["version"] = DATA_VERSION
    return raw


def _fix_nodes(nodes):
    for n in nodes:
        n.setdefault("id", new_id())
        n.setdefault("title", "")
        n.setdefault("content", "")
        n.setdefault("rich", [])
        n.setdefault("updated", stamp())
        n.setdefault("expanded", True)
        n.setdefault("children", [])
        _fix_nodes(n["children"])


def load_data() -> dict:
    """优先读主文件，损坏时回退到备份；旧结构自动迁移。"""
    raw = None
    for path in (DATA_FILE, DATA_FILE.with_name(DATA_FILE.name + ".bak")):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            break
        except Exception:
            raw = None
    if raw is not None:
        try:
            raw = _migrate(raw)
            base = default_data()
            for k, v in base.items():
                raw.setdefault(k, v)
            if not raw.get("books"):
                raw["books"] = base["books"]
            if find_note(raw["books"], raw.get("active_note")) is None:
                raw["active_note"] = first_note_id(raw["books"])
            if raw.get("active_book") is None:
                hit = find_note(raw["books"], raw.get("active_note"))
                raw["active_book"] = hit[0]["id"] if hit else raw["books"][0]["id"]
            if not raw.get("tasks"):
                raw["tasks"] = []
            raw["ui"].update(
                {k: v for k, v in base["ui"].items() if k not in raw["ui"]})
            return raw
        except Exception:
            pass
    return default_data()


def save_data(data: dict) -> None:
    """先备份上一份，再原子写入，任一环节失败都不抛出。"""
    try:
        if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
            bak = DATA_FILE.with_name(DATA_FILE.name + ".bak")
            try:
                shutil.copyfile(DATA_FILE, bak)
            except Exception:
                pass
        tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, DATA_FILE)
    except Exception as exc:
        print("保存失败:", exc, file=sys.stderr)
