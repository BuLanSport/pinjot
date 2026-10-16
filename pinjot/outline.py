# -*- coding: utf-8 -*-
"""大纲标记引擎（纯逻辑，无 UI 依赖）。

支持两类列表，内容以纯文本存储：缩进表达层级，前缀表达列表类型。

    数字编号：                    符号列表：
    1. 无人机结构的原理            • 机架分类
        1.1 机架                      ◦ 四轴
        1.2 动力系统                  ◦ 六轴
    2. 飞控                        • 动力系统

约定
----
* 一级缩进 = 4 个空格。
* 数字编号 = 层级路径（1. / 1.1. / 1.2.1.），每段 ≤3 位、最多 4 段，
  避免把日期（2026.10.10）误认成编号；编号后跟一个空格。
* 符号列表按层级用 •/◦/▪，识别同样只认这三个符号。
* 数字/符号段数与缩进层级矛盾（如行首 "10.24 xxx"）视为普通文本，原样保留。
* 空行不打断列表，普通文本行会打断。
* 数字与符号是两套独立体系：Tab 只在同类型相邻行之间寻父；互不干扰。
* 块的首行原样保留作为基准，后续行按层级重算——删除中间行后编号自动补齐。
"""

import re

INDENT = "    "                     # 一级缩进
INDENT_N = len(INDENT)
MAX_DEPTH = 4                       # 数字编号最多 4 段
BULLETS = ("•", "◦", "▪")           # 第 1/2/3+ 层符号

# 数字行：缩进 + 数字段（每段 ≤3 位，最多 4 段，尾点可省）+ 空白分隔或行尾
NUM_RE = re.compile(
    r"^(\s*)(\d{1,3}(?:\.\d{1,3}){0,%d})(\.?)([ \t]+|$)" % (MAX_DEPTH - 1))
# 符号行：缩进 + •/◦/▪ + 空白分隔或行尾
BULLET_RE = re.compile(r"^(\s*)([•◦▪])([ \t]+|$)")


def parse(line):
    """解析一行。

    返回 (kind, indent, marker, sep, content)；不是列表行则返回 None。
    kind: "num"（数字编号）或 "bullet"（符号列表）；marker: "1.2." / "•"。
    """
    m = NUM_RE.match(line)
    if m:
        indent, body, dot, sep = m.groups()
        return "num", indent, body + dot, sep, line[m.end():]
    m = BULLET_RE.match(line)
    if m:
        indent, sym, sep = m.groups()
        return "bullet", indent, sym, sep, line[m.end():]
    return None


def path_of(num):
    """'1.2.3.' -> [1, 2, 3]"""
    return [int(x) for x in num.rstrip(".").split(".")]


def num_prefix(path):
    """路径 -> 规范前缀，如 [1, 2] -> '    1.2. '"""
    return INDENT * (len(path) - 1) + ".".join(map(str, path)) + ". "


def bullet_prefix(level, sym=None):
    """层级 -> 符号前缀，如 1 -> '    ◦ '"""
    if sym is None:
        sym = BULLETS[min(level, len(BULLETS) - 1)]
    return INDENT * level + sym + " "


def renumber(text):
    """把全文列表标记重排成规范状态（幂等）。

    返回需要修改的行：[(行号从 0 计, 新行文本, 旧前缀长度, 新前缀长度)]。
    前缀长度 = 缩进 + 标记 + 分隔空白的总长，供调用方平移光标。
    """
    lines = text.split("\n")
    changes = []
    counters = []                     # 数字体系：各层最后一个编号
    prev_num_level = -1               # 上一个数字行的层级
    prev_bullet_level = -1            # 上一个符号行的层级
    for i, line in enumerate(lines):
        p = parse(line)
        if p is None:
            if line.strip():
                prev_num_level = prev_bullet_level = -1   # 普通行打断
            continue                                  # 空行不打断
        kind, indent, marker, sep, content = p
        raw_level = len(indent) // INDENT_N
        old_len = len(indent) + len(marker) + len(sep)

        if kind == "num":
            path = path_of(marker)
            if len(path) != raw_level + 1:
                prev_num_level = -1               # 段数与缩进矛盾：普通文本
                continue
            if prev_num_level < 0:
                level = raw_level                 # 块首：编号原样保留作基准
                counters = list(path)
            else:
                level = min(raw_level, prev_num_level + 1)
                del counters[level + 1:]
                while len(counters) <= level:
                    counters.append(0)
                counters[level] += 1
                path = counters[:level + 1]
            prev_num_level = level
            new_prefix = num_prefix(path)
        else:  # bullet
            if prev_bullet_level < 0:
                level = raw_level                 # 块首：缩进原样保留
            else:
                level = min(raw_level, prev_bullet_level + 1)
            prev_bullet_level = level
            new_prefix = bullet_prefix(level)

        new_line = new_prefix + content
        if new_line != line:
            changes.append((i, new_line, old_len, len(new_prefix)))
    return changes


def _prev_num(lines, start):
    """向上找最近的数字行；返回 (缩进层级, 路径) 或 None。

    普通文本行打断；空行与符号行跳过（与 renumber 的块语义一致）。
    """
    for j in range(start, -1, -1):
        p = parse(lines[j])
        if p is None:
            if lines[j].strip():
                return None
            continue                                  # 空行跳过
        kind, indent, marker, _, _ = p
        if kind != "num":
            continue                                  # 符号行跳过
        path = path_of(marker)
        level = len(indent) // INDENT_N
        if len(path) != level + 1:
            return None                               # 伪编号行打断
        return level, path
    return None


def _prev_bullet_level(lines, start):
    """向上找最近的符号行层级；普通文本/伪行打断，数字行与空行跳过。"""
    for j in range(start, -1, -1):
        p = parse(lines[j])
        if p is None:
            if lines[j].strip():
                return None
            continue
        kind, indent, _, _, _ = p
        if kind != "bullet":
            continue                                  # 数字行跳过
        return len(indent) // INDENT_N
    return None


def shifted_prefix(text, line_no, delta):
    """第 line_no 行（从 1 计）层级升降后的新前缀。

    delta=+1 表示降为上一同类型列表项的子节点（Tab），-1 表示升一级
    （Shift+Tab）。返回 (新前缀, 旧前缀长度)；不能移动返回 None。
    """
    lines = text.split("\n")
    if not 1 <= line_no <= len(lines):
        return None
    p = parse(lines[line_no - 1])
    if p is None:
        return None
    kind, indent, marker, sep, _ = p
    raw_level = len(indent) // INDENT_N
    new_level = raw_level + delta
    if new_level < 0 or new_level + 1 > MAX_DEPTH:
        return None
    old_len = len(indent) + len(marker) + len(sep)

    if kind == "num":
        path = path_of(marker)
        if len(path) != raw_level + 1:
            return None                   # 伪编号行不参与
        prev = _prev_num(lines, line_no - 2)
        if prev is None:
            return None                   # 前面没有数字行，无处安放
        prev_level, prev_path = prev
        if delta > 0 and new_level > prev_level + 1:
            return None                   # 不能比上一行的子节点更深
        if new_level <= prev_level:
            new_path = prev_path[:new_level] + [prev_path[new_level] + 1]
        else:
            new_path = prev_path + [1]    # 成为上一数字行的子项
        return num_prefix(new_path), old_len

    # bullet：符号由层级决定；无同类前驱时允许首行降级
    prev_level = _prev_bullet_level(lines, line_no - 2)
    if delta > 0 and prev_level is not None and new_level > prev_level + 1:
        return None
    return bullet_prefix(new_level), old_len
