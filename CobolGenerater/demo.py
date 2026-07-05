"""命令行演示：模拟 GUI 的完整操作流程。"""
import os
import sys

# 兼容打包后的路径
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_parser import build_output_config, parse_csv
from generator import build_program, generate_cobol, save_cobol


def main():
    csv_path = input("请输入 CSV 文件路径（默认：../dataSet/inputTest01.csv）：").strip()
    if not csv_path:
        csv_path = "../dataSet/inputTest01.csv"

    program_id = input("请输入 Program-ID（默认：GEN0001）：").strip()
    if not program_id:
        program_id = "GEN0001"

    out_dir = input("请输入输出目录（默认：../test）：").strip()
    if not out_dir:
        out_dir = "../test"

    print("\n【步骤 1】导入 CSV 并自动推断字段...")
    input_cfg = parse_csv(csv_path)
    print(f"  文件：{input_cfg.file_path}")
    print(f"  记录长度估算：{input_cfg.record_length}")
    print(f"  字段数：{len(input_cfg.fields)}")
    print("\n  字段名              PIC            类型")
    print("  " + "-" * 45)
    for f in input_cfg.fields:
        print(f"  {f.name:18} {f.pic:14} {f.field_type}")

    print("\n【步骤 2】构造输出文件配置...")
    output_cfg = build_output_config(input_cfg)
    print(f"  输出文件名：{output_cfg.file_path}")

    print("\n【步骤 3】生成 COBOL 程序...")
    program = build_program(program_id, input_cfg, output_cfg, remarks="MVP 自动生成")
    code = generate_cobol(program)
    print(f"  生成完成，共 {len(code.splitlines())} 行代码")

    print("\n【步骤 4】保存 .cbl 文件...")
    safe_id = "".join(c for c in program_id if c.isalnum() or c == "_")
    output_path = os.path.join(out_dir, f"{safe_id}.cbl")
    saved = save_cobol(code, output_path)
    print(f"  已保存：{saved}")

    print("\n【生成的 COBOL 源码预览】")
    print("=" * 70)
    print(code)
    print("=" * 70)


if __name__ == "__main__":
    main()
