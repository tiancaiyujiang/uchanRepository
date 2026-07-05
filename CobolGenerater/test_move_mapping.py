"""临时测试脚本：验证 MOVE 节点使用字段映射。"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import LogicStep, Operand, MappingRule, CobolProgram, FileDefinition, CopybookField
from logic_editor import _EditMoveDialog
from logic_generator import render_steps


def test_move_generate():
    step = LogicStep(
        id="m1",
        step_type="MOVE",
        mapping_rules=[
            MappingRule(source=Operand("FIELD", "A"), target=Operand("FIELD", "B")),
            MappingRule(source=Operand("LITERAL", "SPACE"), target=Operand("FIELD", "C")),
        ],
    )
    code = render_steps([step], indent=8)
    print(code)
    assert "MOVE A TO B" in code
    assert "MOVE SPACE TO C" in code
    print("move generate test passed")


def test_move_dialog():
    root = tk.Tk()
    program = CobolProgram(program_id="TEST")
    program.input_files.append(FileDefinition(name="IN", physical_name="IN", file_status="FS", copybook_name="IN", prefix="I", is_input=True))
    program.input_files[0].fields.append(CopybookField(level=3, name="A", full_name="I-A", pic="X(10)"))
    program.output_files.append(FileDefinition(name="OUT", physical_name="OUT", file_status="FS", copybook_name="OUT", prefix="O", is_input=False))
    program.output_files[0].fields.append(CopybookField(level=3, name="A", full_name="O-A", pic="X(10)"))

    step = LogicStep(id="m1", step_type="MOVE")
    dlg = _EditMoveDialog(root, step, program)
    dlg.update_idletasks()
    dlg._auto_map()
    assert len(dlg.rules) == 1, len(dlg.rules)
    dlg._ok()
    assert len(step.mapping_rules) == 1
    print("move dialog test passed")
    root.destroy()


if __name__ == "__main__":
    test_move_generate()
    test_move_dialog()
