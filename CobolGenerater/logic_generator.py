"""将 LogicStep 模型渲染为 COBOL 代码。"""
from typing import List

from models import Condition, EvaluateCase, LogicStep, Operand


def render_steps(steps: List[LogicStep], indent: int = 8) -> str:
    """渲染一组步骤，返回 COBOL 代码文本。"""
    lines = _render_steps_list(steps, indent, terminate=True)
    return "\n".join(lines)


def render_procedure(proc, indent: int = 11) -> str:
    """把一个 Procedure 渲染为一个 COBOL SECTION。"""
    p = _pad(indent)
    header_pad = _pad(max(0, indent - 4))  # SECTION/段名缩进到 AREA A
    lines = [
        f"{header_pad}{proc.name} SECTION.",
        f"{header_pad}{proc.name}-010.",
    ]
    if proc.steps:
        lines.extend(_render_steps_list(proc.steps, indent, True))
    else:
        lines.append(f"{p}CONTINUE")
    lines.append(f"{header_pad}{proc.name}-999.")
    lines.append(f"{p}EXIT.")
    return "\n".join(lines)


def render_procedures(procs, indent: int = 11) -> str:
    """渲染全部 Procedure，每个 PROC 前带三段式注释分隔。"""
    parts = []
    for proc in procs:
        header = [
            "      *>*****************************************************************",
            f"      *>     {proc.name.upper():<64}*",
            "      *>*****************************************************************",
        ]
        parts.append("\n".join(header) + "\n" + render_procedure(proc, indent))
    return "\n\n".join(parts)


def _render_steps_list(steps: List[LogicStep], indent: int, terminate: bool) -> List[str]:
    lines = []
    for step in steps:
        lines.extend(_render_step(step, indent, terminate))
    return lines


def _pad(indent: int) -> str:
    return " " * indent


def _operand_str(op: Operand) -> str:
    if op.op_type == "LITERAL":
        val = op.value.strip()
        if val.upper() in ("SPACE", "SPACES", "ZERO", "ZEROS", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE", "HIGH-VALUES"):
            return val.upper()
        if op.literal_type == "NUMERIC":
            return val
        return f"'{val}'"
    return op.value


def _cond_str(c: Condition) -> str:
    if not c:
        return ""
    return f"{_operand_str(c.left)} {c.operator} {_operand_str(c.right)}"


def _cond_str_list(conditions: List[Condition]) -> str:
    """把多个 Condition 按 logical_op 连接成字符串（AND/OR）。"""
    if not conditions:
        return ""
    parts = []
    for i, c in enumerate(conditions):
        parts.append(_cond_str(c))
        if i < len(conditions) - 1:
            parts.append(c.logical_op or "AND")
    return " ".join(parts)


def _compute_expression_str(step: LogicStep) -> str:
    """把 COMPUTE 的运算单元与运算符列表拼接成表达式字符串。"""
    operands = step.compute_operands
    operators = step.compute_operators
    if len(operands) < 2:
        return "0"
    parts = [_operand_str(operands[0])]
    for i, op in enumerate(operators):
        if i + 1 >= len(operands):
            break
        parts.append(op)
        parts.append(_operand_str(operands[i + 1]))
    return " ".join(parts)


def _stmt(text: str, terminate: bool) -> str:
    """根据是否需要句点返回语句。"""
    return f"{text}{'.' if terminate else ''}"


def _render_step(step: LogicStep, indent: int, terminate: bool) -> List[str]:
    p = _pad(indent)
    lines = []

    if step.step_type == "IF":
        lines.append(f"{p}IF {_cond_str_list(step.conditions)}")
        lines.append(f"{p}  THEN")
        lines.extend(_render_steps_list(step.then_body, indent + 4, False))
        if step.else_body:
            lines.append(f"{p}  ELSE")
            lines.extend(_render_steps_list(step.else_body, indent + 4, False))
        lines.append(_stmt(f"{p}END-IF", terminate))

    elif step.step_type == "EVALUATE":
        is_true_mode = step.evaluate_subject and step.evaluate_subject.op_type == "TRUE"
        if is_true_mode:
            lines.append(f"{p}EVALUATE TRUE")
        else:
            subject = _operand_str(step.evaluate_subject) if step.evaluate_subject else "TRUE"
            lines.append(f"{p}EVALUATE {subject}")
        for case in step.evaluate_cases:
            if case.conditions:
                if is_true_mode:
                    conds = _cond_str_list(case.conditions)
                else:
                    # 目标模式：只取右值，多个值用 ALSO 连接
                    conds = " ALSO ".join(
                        _operand_str(c.right) if c.right else "?" for c in case.conditions
                    )
                lines.append(f"{p}  WHEN {conds}")
            else:
                lines.append(f"{p}  WHEN OTHER")
            lines.extend(_render_steps_list(case.body, indent + 4, False))
        lines.append(_stmt(f"{p}END-EVALUATE", terminate))

    elif step.step_type == "COMPUTE":
        tgt = _operand_str(step.compute_target) if step.compute_target else "?"
        expr = _compute_expression_str(step)
        lines.append(_stmt(f"{p}COMPUTE {tgt} = {expr}", terminate))

    elif step.step_type == "PERFORM":
        if step.perform_type.upper() == "SECTION":
            lines.append(_stmt(f"{p}PERFORM {step.perform_target}", terminate))
        elif step.perform_type.upper() == "UNTIL":
            lines.append(f"{p}PERFORM WITH TEST BEFORE")
            lines.append(f"{p}  UNTIL {_cond_str(step.perform_condition)}")
            lines.extend(_render_steps_list(step.perform_body, indent + 6, False))
            lines.append(_stmt(f"{p}END-PERFORM", terminate))
        elif step.perform_type.upper() == "TIMES":
            lines.append(_stmt(f"{p}PERFORM {step.perform_target} TIMES", terminate))
        else:
            lines.append(_stmt(f"{p}PERFORM {step.perform_target}", terminate))

    elif step.step_type == "MOVE":
        if step.mapping_rules:
            for rule in step.mapping_rules:
                src = _operand_str(rule.source) if rule.source else "?"
                tgt = _operand_str(rule.target) if rule.target else "?"
                lines.append(f"{p}MOVE {src} TO {tgt}")
            if terminate:
                lines[-1] = lines[-1] + "."
        else:
            lines.append(_stmt(f"{p}MOVE ? TO ?", terminate))

    elif step.step_type == "INITIALIZE":
        targets = ", ".join(_operand_str(o) for o in step.initialize_targets)
        lines.append(_stmt(f"{p}INITIALIZE {targets}", terminate))

    elif step.step_type == "CALL":
        using = ""
        if step.call_using:
            using = " USING " + ", ".join(_operand_str(o) for o in step.call_using)
        lines.append(_stmt(f"{p}CALL '{step.call_program}'{using}", terminate))

    elif step.step_type == "CONTINUE":
        lines.append(_stmt(f"{p}CONTINUE", terminate))

    elif step.step_type == "SECTION":
        # 在 PROC 内部把 SECTION 节点渲染为可 PERFORM 的段落，避免嵌套 SECTION
        header_pad = _pad(max(0, indent - 4))
        lines.append(f"{header_pad}{step.label}.")
        lines.extend(_render_steps_list(step.children, indent, True))

    elif step.step_type == "PARAGRAPH":
        lines.append(f"{step.label}.")
        lines.extend(_render_steps_list(step.children, indent, True))

    else:
        lines.append(f"{p}*{step.step_type} not supported yet")

    return lines
