"""COBOL COPYBOOK 解析器。"""
import os
import re
from typing import List, Optional

from models import CopybookField, FileDefinition


def _strip_comments_and_number(line: str) -> str:
    """去掉行号与注释标记，返回有效内容。"""
    if len(line) > 6 and line[6] in "*/D":
        return ""
    # 去掉前 6 列行号
    content = line[6:] if len(line) > 6 else line
    return content.rstrip()


def _extract_pic_length(pic: str) -> int:
    """根据 PIC 计算字段长度（MVP 支持常见格式）。"""
    pic = pic.upper().replace(" ", "")
    # 去掉 COMP 相关后缀
    pic = re.sub(r"COMP-?[0-9A-Z]*", "", pic)
    pic = re.sub(r"BINARY|PACKED-DECIMAL|USAGE.*", "", pic)

    total = 0
    # 匹配 X(n)、9(n)、S9(n)V9(m)、9(n).9(m) 等
    tokens = re.findall(r"(S?9|X|A|N)\(?([^)]*)\)?", pic)
    if not tokens:
        # 单个 X 或 9
        if re.fullmatch(r"S?9", pic):
            return 1
        if re.fullmatch(r"X|A|N", pic):
            return 1
        return 0

    for base, inner in tokens:
        if inner:
            # 可能是 "5" 或 "5.2"
            parts = inner.split(".")
            if len(parts) == 2:
                total += int(parts[0]) + int(parts[1])
            else:
                total += int(parts[0])
        else:
            total += 1
    return total


def parse_copybook(file_path: str, prefix: str = "") -> List[CopybookField]:
    """解析单个 COPYBOOK 文件，返回字段列表。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"COPYBOOK 不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.readlines()

    fields: List[CopybookField] = []
    level_stack: List[tuple[int, str]] = []  # (level, name)
    current_pos = 1

    for raw_line in raw_lines:
        line = _strip_comments_and_number(raw_line)
        if not line.strip():
            continue

        # 取第一个词作为 level number
        parts = line.split(None, 2)
        if not parts or not parts[0].isdigit():
            continue
        level = int(parts[0])

        # 02/01 级通常是记录名，不视为普通字段，但记录下来
        name = parts[1].rstrip(".") if len(parts) > 1 else ""
        rest = parts[2] if len(parts) > 2 else ""

        if not name:
            continue

        # 处理 REDEFINES / OCCURS
        redefines = None
        occurs = 0
        if "REDEFINES" in rest.upper():
            m = re.search(r"REDEFINES\s+(\S+)", rest, re.I)
            if m:
                redefines = m.group(1).rstrip(".")
        if "OCCURS" in rest.upper():
            m = re.search(r"OCCURS\s+(\d+)", rest, re.I)
            if m:
                occurs = int(m.group(1))

        # 提取 PIC
        pic = ""
        m = re.search(r"PIC\s+([^\s.]+(?:\.[^\s.]+)?)", rest, re.I)
        if m:
            pic = m.group(1)

        # 维护层级栈
        while level_stack and level_stack[-1][0] >= level:
            level_stack.pop()
        parent = level_stack[-1][1] if level_stack else None
        level_stack.append((level, name))

        # 计算长度
        length = _extract_pic_length(pic) if pic else 0
        if length == 0 and level > 1:
            # 可能是组项，长度为子字段之和（后续再算）
            pass

        full_name = f"{prefix}-{name}" if prefix else name
        field = CopybookField(
            name=name,
            full_name=full_name,
            pic=pic,
            level=level,
            parent=parent,
            start_pos=current_pos,
            length=length,
            redefines=redefines,
            occurs=occurs,
        )
        fields.append(field)

        if pic:
            current_pos += length

    # 第二次遍历：为组项补齐长度（子字段长度之和）
    _fill_group_lengths(fields)
    return fields


def _fill_group_lengths(fields: List[CopybookField]):
    """根据子字段为组项填充长度。"""
    # 自底向上：按层级降序
    for i in range(len(fields) - 1, -1, -1):
        f = fields[i]
        if f.level <= 1 or f.length > 0:
            continue
        children = [c for c in fields if c.parent == f.name]
        f.length = sum(c.length * max(1, c.occurs) for c in children)


def build_file_definition(
    logical_name: str,
    physical_name: str,
    file_status: str,
    copybook_name: str,
    prefix: str,
    copybook_path: str,
    is_input: bool = True,
) -> FileDefinition:
    """根据 COPYBOOK 构建文件定义。"""
    fields = parse_copybook(copybook_path, prefix=prefix)
    record_name = ""
    for f in fields:
        if f.level == 1:
            record_name = f.full_name
            break
    if not record_name:
        record_name = f"{prefix}-REC" if prefix else f"{logical_name}-REC"

    return FileDefinition(
        name=logical_name,
        physical_name=physical_name,
        file_status=file_status,
        copybook_name=copybook_name,
        prefix=prefix,
        record_name=record_name,
        fields=fields,
        is_input=is_input,
    )
