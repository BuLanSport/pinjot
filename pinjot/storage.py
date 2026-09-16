# -*- coding: utf-8 -*-
"""数据持久化：JSON 读写 + 原子替换 + 滚动备份。"""

import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from .config import APP_NAME, DEF_W, DEF_H, WELCOME


LEGACY_APP_DIRS = ("PinNote",)   # 旧版本的数据目录，首次启动自动迁移


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


def default_data() -> dict:
    nid = new_id()
    return {
        "version": 1,
        "notes": [{"id": nid, "title": "欢迎使用",
                   "content": WELCOME, "updated": stamp()}],
        "active_note": nid,
        "tasks": [
            {"id": new_id(), "text": "把 PinNote 钉在屏幕角落",
             "done": True, "created": stamp()},
            {"id": new_id(), "text": "写下今天要做的三件事",
             "done": False, "created": stamp()},
        ],
        "ui": {
            "x": None, "y": None, "w": DEF_W, "h": DEF_H,
            "topmost": True, "collapsed": False, "tab": "note",
            "opacity": 1.0, "font_size": 10,
        },
    }


def load_data() -> dict:
    """优先读主文件，损坏时回退到备份。"""
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
            base = default_data()
            for k, v in base.items():
                raw.setdefault(k, v)
            if not raw.get("notes"):
                raw["notes"] = base["notes"]
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
