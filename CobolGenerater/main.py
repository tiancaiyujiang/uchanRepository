"""COBOL Generator - 图形界面主入口。"""
import os
import tkinter as tk
import uuid
from typing import List

import customtkinter as ctk

from file_editor import CustomVariableEditor, DataPreviewFrame, FileListEditor
from generator import generate_cobol, save_cobol
from logic_editor import NodeEditor, ProcedureListFrame
from logic_generator import render_steps
from models import CobolProgram, Condition, CustomVariable, FileDefinition, LogicStep, MappingRule, Operand, Procedure


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("COBOL 代码生成器 - KWBAC1 迭代版")
        self.geometry("1400x950")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.program = CobolProgram(program_id="KWBAC1")
        self.generated_code = ""

        # 默认给一个输入输出文件
        self.program.input_files.append(FileDefinition(
            name="KWFAC0", physical_name="SYS010-DA-DK-S",
            file_status="W-FS-KWFAC0", copybook_name="", prefix="FI01", is_input=True
        ))
        self.program.output_files.append(FileDefinition(
            name="KWFAC1", physical_name="SYS020-DA-DK-S",
            file_status="W-FS-KWFAC1", copybook_name="", prefix="FO01", is_input=False
        ))

        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="COBOL 代码生成器（COPYBOOK + 拖拽逻辑编辑器）",
            font=("Microsoft YaHei", 20, "bold"),
        )
        title.pack(pady=10)

        self.tabview = ctk.CTkTabview(self, command=self._on_tab_change)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=10)

        self.tab_files = self.tabview.add("文件定义")
        self.tab_logic = self.tabview.add("逻辑编辑器")
        self.tab_preview = self.tabview.add("代码预览")

        self._build_files_tab()
        self._build_logic_tab()
        self._build_preview_tab()

    def _on_tab_change(self):
        name = self.tabview.get()
        if name == "逻辑编辑器":
            self.proc_list.refresh()
            self._refresh_logic_preview()

    def _build_files_tab(self):
        # 左右分栏：左侧文件定义 + 自定义变量，右侧 DATA 预览
        paned = ctk.CTkFrame(self.tab_files)
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkScrollableFrame(paned, width=850)
        left.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        right = ctk.CTkFrame(paned, width=450)
        right.pack(side="right", fill="y", padx=5, pady=5)

        self.input_editor = FileListEditor(left, "input_files", True, self.program)
        self.input_editor.pack(fill="x", padx=5, pady=5)

        self.output_editor = FileListEditor(left, "output_files", False, self.program)
        self.output_editor.pack(fill="x", padx=5, pady=5)

        self.var_editor = CustomVariableEditor(left, self.program, on_change=self._on_data_change)
        self.var_editor.pack(fill="x", padx=5, pady=5)

        self.data_preview = DataPreviewFrame(right, lambda: self._get_program_for_preview())
        self.data_preview.pack(fill="both", expand=True)

        btn_frame = ctk.CTkFrame(left)
        btn_frame.pack(fill="x", padx=5, pady=10)
        ctk.CTkButton(btn_frame, text="保存文件定义并刷新预览", command=self._refresh_data_preview).pack(side="left", padx=10)

    def _get_program_for_preview(self) -> CobolProgram:
        self.input_editor.save_all()
        self.output_editor.save_all()
        return self.program

    def _on_data_change(self):
        self._refresh_data_preview()

    def _refresh_data_preview(self):
        self.input_editor.save_all()
        self.output_editor.save_all()
        self.data_preview.refresh()

    def _build_logic_tab(self):
        ctk.CTkLabel(self.tab_logic, text="拖拽节点编排处理逻辑（按 PROC 组织）", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        btn_frame = ctk.CTkFrame(self.tab_logic)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_frame, text="生成 BUNPAI 模板", command=self._load_bunpai_template).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="刷新逻辑预览", command=self._refresh_logic_preview).pack(side="left", padx=5)

        # 默认至少存在一个 PROC（CUSTOM-EDIT-PROC）
        if not self.program.procedures:
            self.program.procedures.append(
                Procedure(id=str(uuid.uuid4())[:8], name="CUSTOM-EDIT-PROC", title="自定义编辑处理", call_point="LOOP")
            )

        # 左右分栏：左侧 PROC 列表，右侧画布
        paned = ctk.CTkFrame(self.tab_logic)
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        self.proc_list = ProcedureListFrame(
            paned, self.program,
            on_select=self._on_proc_select,
            on_change=self._on_logic_change,
            width=220,
        )
        self.proc_list.pack(side="left", fill="y", padx=5, pady=5)

        editor_frame = ctk.CTkFrame(paned)
        editor_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.current_procedure = self.program.procedures[0]
        self.node_editor = NodeEditor(
            editor_frame, self.current_procedure.steps,
            program=self.program,
            on_change=self._on_logic_change,
        )
        self.node_editor.pack(fill="both", expand=True)

        ctk.CTkLabel(self.tab_logic, text="逻辑代码预览", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.logic_preview = ctk.CTkTextbox(self.tab_logic, height=200, font=("Consolas", 10), wrap="none")
        self.logic_preview.pack(fill="x", padx=10, pady=5)
        self._refresh_logic_preview()

    def _on_proc_select(self, proc: Procedure):
        # 切换当前 PROC 前，把画布上的步骤同步回上一个 PROC
        if self.current_procedure:
            self.current_procedure.steps = self.node_editor.get_steps()
        self.current_procedure = proc
        self.node_editor.set_steps(proc.steps)
        self._refresh_logic_preview()

    def _load_bunpai_template(self):
        def make_move(src, tgt, src_type="FIELD"):
            return LogicStep(
                id=str(uuid.uuid4())[:8], step_type="MOVE",
                mapping_rules=[MappingRule(source=Operand(src_type, src), target=Operand("FIELD", tgt))]
            )

        def make_if(cond, then_moves, else_steps=None):
            s = LogicStep(id=str(uuid.uuid4())[:8], step_type="IF", conditions=[cond])
            for src, tgt in then_moves:
                s.then_body.append(make_move(src, tgt))
            if else_steps:
                s.else_body.extend(else_steps)
            return s

        outer = make_if(
            Condition(Operand("FIELD", "FI01-HHS-BNG"), "=", Operand("FIELD", "WK01-BK-HHS-BNG")),
            [],
            [make_move("FI01-HHS-BNG", "WK01-BK-HHS-BNG")]
        )

        then_if = make_if(
            Condition(Operand("FIELD", "FI01-HHS-IDO-YMD"), ">=", Operand("FIELD", "WK01-CDATE")),
            [("CON-1-AL", "WK01-WRT-FLG")],
            [make_move("SPACE", "WK01-WRT-FLG", "LITERAL")]
        )
        outer.then_body.append(then_if)

        inner_if = make_if(
            Condition(Operand("FIELD", "FI01-HHS-SKSS-YMD"), "=", Operand("LITERAL", "SPACE")),
            [("CON-1-AL", "WK01-WRT-FLG")],
            [make_if(
                Condition(Operand("FIELD", "FI01-HHS-IDO-YMD"), ">=", Operand("FIELD", "WK01-CDATE")),
                [("CON-1-AL", "WK01-WRT-FLG")],
                [make_move("SPACE", "WK01-WRT-FLG", "LITERAL")]
            )]
        )
        outer.else_body.append(inner_if)

        # 把模板逻辑放入当前选中的 PROC（没有则创建默认 CUSTOM-EDIT-PROC）
        if not self.program.procedures:
            self.program.procedures.append(
                Procedure(id=str(uuid.uuid4())[:8], name="CUSTOM-EDIT-PROC", title="自定义编辑处理", call_point="LOOP")
            )
        target = self.current_procedure if self.current_procedure else self.program.procedures[0]
        target.steps = [outer]
        self.node_editor.set_steps(target.steps)
        self.proc_list.refresh()
        self._on_logic_change()

    def _on_logic_change(self):
        if self.current_procedure:
            self.current_procedure.steps = self.node_editor.get_steps()
        self._refresh_logic_preview()

    def _refresh_logic_preview(self):
        from logic_generator import render_procedures
        code = render_procedures(self.program.procedures, indent=8)
        self.logic_preview.delete("1.0", tk.END)
        self.logic_preview.insert("1.0", code if code.strip() else "（暂无 PROC）")

    def _build_preview_tab(self):
        btn_frame = ctk.CTkFrame(self.tab_preview)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(btn_frame, text="生成 COBOL", command=self._generate, height=36).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="保存 .cbl", command=self._save, height=36).pack(side="left", padx=10)

        self.preview_text = ctk.CTkTextbox(self.tab_preview, font=("Consolas", 10), wrap="none")
        self.preview_text.pack(fill="both", expand=True, padx=10, pady=5)

    def _generate(self):
        self.input_editor.save_all()
        self.output_editor.save_all()
        if self.current_procedure:
            self.current_procedure.steps = self.node_editor.get_steps()
        try:
            self.generated_code = generate_cobol(self.program, inline_copybooks=True)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", self.generated_code)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("生成失败", str(e))

    def _save(self):
        if not self.generated_code:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先生成代码")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".cbl",
            filetypes=[("COBOL 文件", "*.cbl"), ("所有文件", "*.*")],
            initialfile=f"{self.program.program_id}.cbl",
        )
        if path:
            try:
                save_cobol(self.generated_code, path)
                from tkinter import messagebox
                messagebox.showinfo("成功", f"已保存到:\n{path}")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("保存失败", str(e))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
