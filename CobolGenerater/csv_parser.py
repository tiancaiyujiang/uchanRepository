"""CSV 解析与字段推断。"""
import csv
import os
from typing import List

from models import CopybookField, Field, FileConfig


def infer_pic(value: str) -> tuple[str, int, str]:
    """根据样本值推断 PIC 类型、长度与数据类型。"""
    value = value.strip()
    if not value:
        return "X(20)", 20, "string"

    # 尝试整数
    if value.lstrip("-").isdigit():
        length = max(len(value), 5)
        return f"9({length})", length, "integer"

    # 尝试小数（隐含小数点 V）
    cleaned = value.replace(".", "", 1).lstrip("-")
    if cleaned.isdigit() and "." in value:
        int_part = len(value.split(".")[0].lstrip("-"))
        dec_part = len(value.split(".")[1])
        int_len = max(int_part, 5)
        dec_len = max(dec_part, 2)
        return f"9({int_len})V9({dec_len})", int_len + dec_len, "decimal"

    # 字符串：按实际长度扩展，至少 20
    length = max(len(value.encode("gbk")), 20)
    return f"X({length})", length, "string"


def parse_csv(csv_path: str, sample_rows: int = 100) -> FileConfig:
    """读取 CSV 文件并推断字段结构。"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"找不到文件: {csv_path}")

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = []
        for idx, row in enumerate(reader):
            if idx >= sample_rows:
                break
            if len(row) == len(headers):
                rows.append(row)

    fields: List[Field] = []
    for col_idx, header in enumerate(headers):
        header = header.strip() or f"COL{col_idx + 1}"

        max_len = 0
        has_string = False
        has_decimal = False
        max_int_digits = 0
        max_dec_digits = 0

        # 用样本值推断 PIC
        for row in rows:
            sample = row[col_idx] if col_idx < len(row) else ""
            inferred_pic, inferred_len, inferred_type = infer_pic(sample)
            max_len = max(max_len, inferred_len)
            if inferred_type == "string":
                has_string = True
            elif inferred_type == "decimal":
                has_decimal = True
                # 解析整数位和小数位
                parts = sample.split(".")
                max_int_digits = max(max_int_digits, len(parts[0].lstrip("-")))
                max_dec_digits = max(max_dec_digits, len(parts[1]))
            elif inferred_type == "integer":
                max_int_digits = max(max_int_digits, inferred_len)

        # 空列默认 string
        if max_len == 0:
            has_string = True
            max_len = len(header)

        # 确定字段类型与 PIC
        if has_string:
            pic = f"X({max(max_len, len(header), 20)})"
            field_type = "string"
            max_len = max(max_len, len(header), 20)
        elif has_decimal:
            int_len = max(max_int_digits, 5)
            dec_len = max(max_dec_digits, 2)
            pic = f"9({int_len})V9({dec_len})"
            field_type = "decimal"
            max_len = int_len + dec_len
        else:
            int_len = max(max_int_digits, 5)
            pic = f"9({int_len})"
            field_type = "integer"
            max_len = int_len

        fields.append(Field(name=header, pic=pic, length=max_len, field_type=field_type, comment=header))

    # 计算记录长度（固定长度近似）
    record_length = sum(f.length for f in fields)

    base_name = os.path.splitext(os.path.basename(csv_path))[0].upper()
    return FileConfig(
        name=f"{base_name}-IN",
        file_path=csv_path,
        record_length=record_length,
        fields=fields,
        is_csv=True,
    )


def build_output_config(input_config: FileConfig, suffix: str = "-OUT") -> FileConfig:
    """根据输入配置生成默认输出配置。"""
    out_name = input_config.name.replace("-IN", "") + suffix
    return FileConfig(
        name=out_name,
        file_path=f"{out_name}.txt",
        record_length=input_config.record_length,
        fields=[Field(name=f.name, pic=f.pic, length=f.length, field_type=f.field_type, comment=f.comment)
                for f in input_config.fields],
        is_csv=False,
    )


def csv_to_copybook_fields(csv_path: str, prefix: str = "") -> List[CopybookField]:
    """读取 CSV 并转换为 CopybookField 列表，用于文件定义编辑器。"""
    cfg = parse_csv(csv_path)
    fields: List[CopybookField] = []
    # 添加 01 级记录名
    rec_name = f"{prefix}-{cfg.name}" if prefix else cfg.name
    fields.append(CopybookField(name=cfg.name, full_name=rec_name, pic="", level=1, length=cfg.record_length))

    pos = 1
    for f in cfg.fields:
        full = f"{prefix}-{f.name}" if prefix else f.name
        fields.append(CopybookField(
            name=f.name,
            full_name=full,
            pic=f.pic,
            level=5,
            start_pos=pos,
            length=f.length,
            comment=f.comment,
        ))
        pos += f.length
    return fields
