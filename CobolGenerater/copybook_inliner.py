"""将 COPYBOOK 内容按前缀内联到生成的 COBOL 中。"""
import re
from typing import List


def inline_copybook(copybook_path: str, prefix: str) -> List[str]:
    """读取 COPYBOOK 并为所有层级字段添加前缀。"""
    with open(copybook_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    result = []
    for raw in lines:
        # 跳过注释行（第7列为 * / D）
        if len(raw) > 6 and raw[6] in "*/D":
            continue
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        # 匹配 level number 和字段名
        m = re.match(r"^(\s*)(\d{2})\s+([A-Z0-9-]+)(.*)$", line)
        if m:
            lead = m.group(1)
            level = m.group(2)
            name = m.group(3)
            rest = m.group(4)
            # COPY PREFIXING 会对所有层级名称加前缀
            new_line = f"{lead}{level}  {prefix}-{name}{rest}"
            result.append(new_line)
        else:
            result.append(line)
    return result
