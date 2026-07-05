"""全流程自测：CSV -> 文件定义 -> 自定义变量 -> 各类型逻辑节点 -> COBOL 编译。"""
import os
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_parser import csv_to_copybook_fields
from generator import generate_cobol
from models import (
    CobolProgram, Condition, CopybookField, CustomVariable, EvaluateCase,
    FileDefinition, LogicStep, MappingRule, Operand, Procedure,
)


def make_operand_field(name: str) -> Operand:
    return Operand("FIELD", name)


def make_operand_literal(value: str, numeric: bool = False) -> Operand:
    return Operand("LITERAL", value, literal_type="NUMERIC" if numeric else "TEXT")


def make_move(src, tgt, src_literal=False, numeric=False) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="MOVE",
        mapping_rules=[MappingRule(
            source=make_operand_literal(src, numeric) if src_literal else make_operand_field(src),
            target=make_operand_field(tgt),
        )],
    )


def make_if(conditions, then_steps, else_steps=None) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="IF",
        conditions=conditions,
        then_body=then_steps,
        else_body=else_steps or [],
    )


def make_evaluate(subject, cases) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="EVALUATE",
        evaluate_subject=subject,
        evaluate_cases=cases,
    )


def make_compute(target, operands, operators) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="COMPUTE",
        compute_target=make_operand_field(target),
        compute_operands=operands,
        compute_operators=operators,
    )


def make_perform_section(target: str) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="PERFORM",
        perform_type="SECTION", perform_target=target,
    )


def make_perform_until(condition, body) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="PERFORM",
        perform_type="UNTIL", perform_condition=condition, perform_body=body,
    )


def make_initialize(targets) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="INITIALIZE",
        initialize_targets=[make_operand_field(t) for t in targets],
    )


def make_call(program, using) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="CALL",
        call_program=program,
        call_using=[make_operand_field(u) for u in using],
    )


def make_section(label, children) -> LogicStep:
    return LogicStep(
        id=str(uuid.uuid4())[:8], step_type="SECTION",
        label=label, children=children,
    )


def build_program(csv_path: str) -> CobolProgram:
    input_fields = csv_to_copybook_fields(csv_path, prefix="FI01")
    output_fields = csv_to_copybook_fields(csv_path, prefix="FO01")
    # 01 级记录名需要替换前缀
    if output_fields:
        output_fields[0].full_name = output_fields[0].full_name.replace("FI01-", "FO01-")

    in_file = FileDefinition(
        name="INFILE", physical_name="INFILE", file_status="W-FS-IN",
        copybook_name="", prefix="FI01", is_input=True, fields=input_fields,
    )
    out_file = FileDefinition(
        name="OUTFILE", physical_name="OUTFILE", file_status="W-FS-OUT",
        copybook_name="", prefix="FO01", is_input=False, fields=output_fields,
    )

    program = CobolProgram(
        program_id="FULLFLOW",
        input_files=[in_file],
        output_files=[out_file],
    )

    # 自定义变量：覆盖不同类型/长度
    program.custom_variables.extend([
        CustomVariable(level="03", name="V-TOTAL", var_type="9", length="7"),
        CustomVariable(level="03", name="V-FLAG", var_type="X", length="1", initial_value="N"),
        CustomVariable(level="03", name="V-COUNT", var_type="9", length="3", initial_value="0"),
    ])

    # 构造一个用户 PROC，包含所有模块各两种
    proc = Procedure(id="p1", name="CUSTOM-EDIT-PROC", title="自定义编辑处理", call_point="LOOP")

    # MOVE x2
    proc.steps.append(make_move("FI01-ID", "FO01-ID"))
    proc.steps.append(make_move("SPACE", "FO01-NAME", src_literal=True))

    # COMPUTE x2
    proc.steps.append(make_compute(
        "V-TOTAL",
        [make_operand_field("FI01-AMOUNT"), make_operand_literal("2", numeric=True)],
        ["*"],
    ))
    proc.steps.append(make_compute(
        "FO01-AMOUNT",
        [make_operand_field("FI01-AMOUNT"), make_operand_field("V-TOTAL")],
        ["+"],
    ))

    # INITIALIZE x2
    proc.steps.append(make_initialize(["FO01-FLAG"]))
    proc.steps.append(make_initialize(["V-COUNT"]))

    # CALL x2
    proc.steps.append(make_call("SUB1", ["FI01-ID"]))
    proc.steps.append(make_call("SUB2", ["V-TOTAL"]))

    # IF x2
    proc.steps.append(make_if(
        [Condition(make_operand_field("FI01-FLAG"), "=", make_operand_literal("A"))],
        [make_move("X", "FO01-STATUS", src_literal=True)],
        [make_move("SPACE", "FO01-STATUS", src_literal=True)],
    ))
    cond1 = Condition(make_operand_field("FI01-AMOUNT"), ">", make_operand_literal("100", numeric=True))
    cond2 = Condition(make_operand_field("FI01-COUNT"), "<", make_operand_literal("5", numeric=True))
    cond2.logical_op = "AND"
    proc.steps.append(make_if(
        [cond1, cond2],
        [make_move("1", "V-COUNT", src_literal=True, numeric=True)],
    ))

    # EVALUATE x2
    proc.steps.append(make_evaluate(
        make_operand_field("FI01-FLAG"),
        [
            EvaluateCase(conditions=[Condition(Operand("FIELD", ""), "=", make_operand_literal("A"))],
                         body=[make_move("A", "FO01-STATUS", src_literal=True)]),
            EvaluateCase(conditions=[Condition(Operand("FIELD", ""), "=", make_operand_literal("B"))],
                         body=[make_move("B", "FO01-STATUS", src_literal=True)]),
            EvaluateCase(conditions=[], body=[make_move("SPACE", "FO01-STATUS", src_literal=True)]),
        ],
    ))
    proc.steps.append(make_evaluate(
        Operand("TRUE", "TRUE"),
        [
            EvaluateCase(conditions=[Condition(make_operand_field("FI01-AMOUNT"), ">", make_operand_literal("0", numeric=True))],
                         body=[make_move("1", "V-COUNT", src_literal=True, numeric=True)]),
            EvaluateCase(conditions=[], body=[make_move("0", "V-COUNT", src_literal=True, numeric=True)]),
        ],
    ))

    # PERFORM x2
    proc.steps.append(make_section("HELPER-PARA", [make_move("FI01-ID", "FO01-ID")]))
    proc.steps.append(make_perform_section("HELPER-PARA"))
    proc.steps.append(make_perform_until(
        Condition(make_operand_field("V-COUNT"), ">", make_operand_literal("0", numeric=True)),
        [make_move("SPACE", "FO01-NAME", src_literal=True)],
    ))

    program.procedures.append(proc)
    return program


def main():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "dataSet", "full_flow_test.csv")
    csv_path = os.path.abspath(csv_path)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("ID,NAME,AMOUNT,FLAG,DATE,STATUS,COUNT\n")
        f.write("1001,Alice,123.45,A,20240101,OK,3\n")
        f.write("1002,Bob,67.8,B,20240102,NG,1\n")

    program = build_program(csv_path)
    code = generate_cobol(program, inline_copybooks=False)

    out_dir = os.path.join(os.path.dirname(__file__), "tmp_test")
    os.makedirs(out_dir, exist_ok=True)
    src_path = os.path.join(out_dir, "fullflow.cbl")
    exe_path = os.path.join(out_dir, "fullflow.exe")
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(code)
    res = subprocess.run(
        ["D:/ZHYCobolGenerator/GC32M-BDB-x64/bin/cobc", "-free", "-x", "-o", exe_path, src_path],
        capture_output=True, text=True,
    )
    print("STDERR:", res.stderr)
    print("RETURN:", res.returncode)
    if res.returncode != 0:
        sys.exit(res.returncode)
    print("全流程编译通过")


if __name__ == "__main__":
    main()
