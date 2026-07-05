"""COBOL 代码生成器。"""
import os
from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from copybook_inliner import inline_copybook
from logic_generator import render_procedures, render_steps
from models import CobolProgram, CustomVariable, FileDefinition


def _ensure_safe_program_id(name: str) -> str:
    """生成合法的 COBOL PROGRAM-ID。"""
    safe = name.strip().upper().replace("-", "_")
    safe = "".join(c for c in safe if c.isalnum() or c == "_")
    if not safe or safe[0].isdigit():
        safe = "PGM" + safe
    return safe[:30]


def get_template_dir() -> str:
    """兼容开发环境和 PyInstaller 打包后的模板路径。"""
    if getattr(__import__("sys"), "frozen", False):
        base_path = __import__("sys")._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "templates")


def generate_cobol(program: CobolProgram, inline_copybooks: bool = True) -> str:
    """根据程序模型生成 COBOL 源码（KWBAC1 框架风格）。
    
    Args:
        inline_copybooks: 是否将 COPYBOOK 内容内联到生成代码中。
                         真实 IBM/Hitachi 环境可设为 False 使用 COPY PREFIXING。
    """
    program.program_id = _ensure_safe_program_id(program.program_id)

    template_dir = get_template_dir()
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("kwbac1_framework.cobol.j2")

    # 确保每个文件定义有记录名
    for f in program.input_files + program.output_files:
        if not f.record_name:
            lvl1 = [fld for fld in f.fields if fld.level == 1]
            if lvl1:
                f.record_name = lvl1[0].full_name
            elif f.fields:
                f.record_name = f.fields[0].full_name
            else:
                f.record_name = f"{f.prefix}-{f.name}-REC" if f.prefix else f"{f.name}-REC"

    # 渲染用户在逻辑编辑器中定义的每个 PROC 为独立 SECTION
    user_procs_code = render_procedures(program.procedures, indent=11)
    user_proc_names = [p.name for p in program.procedures]

    # 预读内联 copybook 内容（供模板使用）
    inlined = {}
    for f in program.input_files + program.output_files:
        if f.copybook_name and inline_copybooks:
            # 尝试在常见位置查找 copybook
            candidates = [
                f"../customerProvideFiles/copybooks/{f.copybook_name}.cpy",
                f"{f.copybook_name}.cpy",
            ]
            path = None
            for c in candidates:
                if os.path.exists(c):
                    path = c
                    break
            if path:
                inlined[f.name] = inline_copybook(path, f.prefix)

    custom_vars_ws = format_custom_variables([v for v in program.custom_variables if v.section == "WORKING-STORAGE"])
    custom_vars_linkage = format_custom_variables([v for v in program.custom_variables if v.section == "LINKAGE"])

    code = template.render(
        program=program,
        user_procs_code=user_procs_code,
        user_proc_names=user_proc_names,
        date_written=datetime.now().strftime("%Y/%m/%d"),
        inline_copybooks=inline_copybooks,
        inlined=inlined,
        custom_vars_ws=custom_vars_ws,
        custom_vars_linkage=custom_vars_linkage,
    )
    if not code.endswith("\n"):
        code += "\n"
    return code


def format_custom_variables(variables: list) -> list[str]:
    """把一组自定义变量格式化为 COBOL 数据定义行。"""
    lines = []
    in_user_group = False
    base_indent = "       "
    for var in variables:
        level = var.level.strip()
        rel_indent = "    " if level not in ("01", "77", "88") else ""
        indent = base_indent + rel_indent
        if level in ("77", "88"):
            in_user_group = False
            lines.append(_format_single_variable(var, indent))
        elif level == "01":
            in_user_group = False
            lines.append(_format_single_variable(var, indent))
        else:
            # 03/05 等需要挂在 01 下
            if not in_user_group:
                lines.append(f"{base_indent}01  USER-VARIABLES.")
                in_user_group = True
            lines.append(_format_single_variable(var, indent))
    return lines


def _format_single_variable(var, indent: str = "       ") -> str:
    pic = var.var_type
    if "(" not in pic and var.length:
        if pic in ("X", "9", "S9"):
            pic = f"{pic}({var.length})"
    line = f"{indent}{var.level:>2}  {var.name:<30} PIC {pic}"
    if var.initial_value:
        val = var.initial_value.strip().upper()
        if val in ("SPACE", "SPACES", "ZERO", "ZEROS", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE", "HIGH-VALUES"):
            line += f"  VALUE {val}"
        elif var.var_type in ("9", "S9") and val.replace("-", "").isdigit():
            line += f"  VALUE {var.initial_value}"
        else:
            line += f"  VALUE '{var.initial_value}'"
    line += "."
    return line


def save_cobol(code: str, output_path: str) -> str:
    """保存 COBOL 源码到文件。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
    return str(output_path)


def build_program(
    program_id: str,
    input_file: FileDefinition,
    output_file: FileDefinition,
    author: str = "COBOL Generator",
    remarks: str = "",
) -> CobolProgram:
    """根据输入输出文件配置构造程序模型。"""
    return CobolProgram(
        program_id=program_id,
        input_files=[input_file],
        output_files=[output_file],
        author=author,
        remarks=remarks,
    )
