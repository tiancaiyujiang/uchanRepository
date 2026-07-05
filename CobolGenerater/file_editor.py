"""输入输出文件与自定义变量编辑器。"""
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, List, Optional

import customtkinter as ctk

from copybook_parser import build_file_definition, parse_copybook
from csv_parser import csv_to_copybook_fields
from models import CopybookField, CobolProgram, CustomVariable, FileDefinition, MappingRule, Operand


class FileCard(ctk.CTkFrame):
    """单个文件定义卡片。"""

    def __init__(self, master, file_def: FileDefinition, on_delete: Callable, **kwargs):
        super().__init__(master, **kwargs)
        self.file_def = file_def
        self.on_delete = on_delete
        self.fields_entries: list[tuple[CopybookField, ctk.CTkEntry]] = []

        self._build_ui()

    def _build_ui(self):
        # 标题 + 删除按钮
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(header, text=f"{'输入' if self.file_def.is_input else '输出'}文件", font=("Microsoft YaHei", 11, "bold")).pack(side="left")
        ctk.CTkButton(header, text="删除", width=60, command=self.on_delete).pack(side="right", padx=5)

        # 基本信息
        grid = ctk.CTkFrame(self)
        grid.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(grid, text="逻辑名").grid(row=0, column=0, padx=5, pady=2)
        self.ent_name = ctk.CTkEntry(grid, width=120)
        self.ent_name.insert(0, self.file_def.name)
        self.ent_name.grid(row=0, column=1, padx=5, pady=2)

        ctk.CTkLabel(grid, text="物理名").grid(row=0, column=2, padx=5, pady=2)
        self.ent_phys = ctk.CTkEntry(grid, width=180)
        self.ent_phys.insert(0, self.file_def.physical_name)
        self.ent_phys.grid(row=0, column=3, padx=5, pady=2)

        ctk.CTkLabel(grid, text="File Status").grid(row=1, column=0, padx=5, pady=2)
        self.ent_fs = ctk.CTkEntry(grid, width=120)
        self.ent_fs.insert(0, self.file_def.file_status)
        self.ent_fs.grid(row=1, column=1, padx=5, pady=2)

        ctk.CTkLabel(grid, text="前缀").grid(row=1, column=2, padx=5, pady=2)
        self.ent_prefix = ctk.CTkEntry(grid, width=120)
        self.ent_prefix.insert(0, self.file_def.prefix)
        self.ent_prefix.grid(row=1, column=3, padx=5, pady=2)

        # COPYBOOK 选项
        # COPYBOOK 选项
        cpy_frame = ctk.CTkFrame(self)
        cpy_frame.pack(fill="x", padx=5, pady=2)
        self.use_copybook = ctk.CTkCheckBox(cpy_frame, text="读取 COPYBOOK")
        self.use_copybook.pack(side="left", padx=5)
        self.ent_cpy = ctk.CTkEntry(cpy_frame, width=300)
        self.ent_cpy.pack(side="left", padx=5)
        ctk.CTkButton(cpy_frame, text="选择", width=60, command=self._select_copybook).pack(side="left", padx=5)
        ctk.CTkButton(cpy_frame, text="解析/加载", width=80, command=self._load_fields).pack(side="left", padx=5)

        if self.file_def.copybook_name:
            self.use_copybook.select()

        # CSV 选项
        csv_frame = ctk.CTkFrame(self)
        csv_frame.pack(fill="x", padx=5, pady=2)
        self.use_csv = ctk.CTkCheckBox(csv_frame, text="读取 CSV")
        self.use_csv.pack(side="left", padx=5)
        self.ent_csv = ctk.CTkEntry(csv_frame, width=300)
        self.ent_csv.pack(side="left", padx=5)
        ctk.CTkButton(csv_frame, text="选择", width=60, command=self._select_csv).pack(side="left", padx=5)
        ctk.CTkButton(csv_frame, text="解析/加载", width=80, command=self._load_csv_fields).pack(side="left", padx=5)

        # 字段编辑区
        ctk.CTkLabel(self, text="字段定义（留空 PIC 表示组项）", font=("Microsoft YaHei", 10)).pack(anchor="w", padx=5, pady=(5, 0))
        self.fields_scroll = ctk.CTkScrollableFrame(self, height=120)
        self.fields_scroll.pack(fill="x", padx=5, pady=2)

        ctk.CTkButton(self, text="+ 添加字段", command=self._add_field_row).pack(anchor="w", padx=5, pady=2)

        self._render_fields()

    def _select_copybook(self):
        path = filedialog.askopenfilename(title="选择 COPYBOOK", filetypes=[("COPYBOOK", "*.cpy"), ("所有文件", "*.*")])
        if path:
            self.ent_cpy.delete(0, tk.END)
            self.ent_cpy.insert(0, path)
            self.use_copybook.select()
            self.use_csv.deselect()

    def _load_fields(self):
        path = self.ent_cpy.get().strip()
        if not path or not self.use_copybook.get():
            return
        try:
            fields = parse_copybook(path, self.ent_prefix.get().strip())
            self.file_def.fields = fields
            self.file_def.copybook_name = Path(path).stem
            self.file_def.record_name = f"{self.ent_prefix.get().strip()}-{Path(path).stem}" if fields and fields[0].level == 1 else f"{self.ent_prefix.get().strip()}-REC"
            self._render_fields()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("解析失败", str(e))

    def _select_csv(self):
        path = filedialog.askopenfilename(title="选择 CSV", filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.ent_csv.delete(0, tk.END)
            self.ent_csv.insert(0, path)
            self.use_csv.select()
            self.use_copybook.deselect()

    def _load_csv_fields(self):
        path = self.ent_csv.get().strip()
        if not path or not self.use_csv.get():
            return
        try:
            prefix = self.ent_prefix.get().strip()
            self.file_def.fields = csv_to_copybook_fields(path, prefix)
            self.file_def.copybook_name = ""  # 清空 copybook 标记
            self._render_fields()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("CSV 解析失败", str(e))

    def _render_fields(self):
        for w in self.fields_scroll.winfo_children():
            w.destroy()
        self.fields_entries.clear()

        headers = ["层级", "字段名", "PIC", "长度"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self.fields_scroll, text=h, font=("Microsoft YaHei", 9, "bold")).grid(row=0, column=col, padx=3, pady=2)

        for row, f in enumerate(self.file_def.fields, start=1):
            ent_level = ctk.CTkEntry(self.fields_scroll, width=50)
            ent_level.insert(0, str(f.level))
            ent_level.grid(row=row, column=0, padx=3, pady=1)

            ent_name = ctk.CTkEntry(self.fields_scroll, width=180)
            ent_name.insert(0, f.name)
            ent_name.grid(row=row, column=1, padx=3, pady=1)

            ent_pic = ctk.CTkEntry(self.fields_scroll, width=120)
            ent_pic.insert(0, f.pic)
            ent_pic.grid(row=row, column=2, padx=3, pady=1)

            ent_len = ctk.CTkEntry(self.fields_scroll, width=60)
            ent_len.insert(0, str(f.length))
            ent_len.grid(row=row, column=3, padx=3, pady=1)

            self.fields_entries.append((f, ent_level, ent_name, ent_pic, ent_len))

    def _add_field_row(self):
        new_field = CopybookField(name="NEW-FIELD", pic="X(20)", level=5, length=20)
        self.file_def.fields.append(new_field)
        self._render_fields()

    def save_to_model(self):
        """把 UI 上的值写回 file_def。"""
        self.file_def.name = self.ent_name.get().strip().upper()
        self.file_def.physical_name = self.ent_phys.get().strip()
        self.file_def.file_status = self.ent_fs.get().strip().upper()
        self.file_def.prefix = self.ent_prefix.get().strip().upper()
        if self.use_copybook.get():
            self.file_def.copybook_name = Path(self.ent_cpy.get().strip()).stem
        else:
            self.file_def.copybook_name = ""

        # 更新字段
        new_fields = []
        for old, ent_level, ent_name, ent_pic, ent_len in self.fields_entries:
            try:
                level = int(ent_level.get())
            except:
                level = old.level
            name = ent_name.get().strip().upper()
            pic = ent_pic.get().strip()
            try:
                length = int(ent_len.get())
            except:
                length = old.length
            full_name = f"{self.file_def.prefix}-{name}" if self.file_def.prefix else name
            new_fields.append(CopybookField(
                name=name,
                full_name=full_name,
                pic=pic,
                level=level,
                parent=old.parent,
                start_pos=old.start_pos,
                length=length,
                comment=old.comment,
            ))
        # 保留未渲染的新增字段（如果有）
        self.file_def.fields = new_fields


class FileListEditor(ctk.CTkFrame):
    """输入或输出文件列表编辑器。"""

    def __init__(self, master, program_attr: str, is_input: bool, program: CobolProgram, **kwargs):
        super().__init__(master, **kwargs)
        self.program_attr = program_attr
        self.is_input = is_input
        self.program = program
        self.cards: List[FileCard] = []
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=5, pady=5)
        label = "输入文件列表" if self.is_input else "输出文件列表"
        ctk.CTkLabel(header, text=label, font=("Microsoft YaHei", 13, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ 添加", command=self._add_file, width=80).pack(side="left", padx=10)

        self.scroll = ctk.CTkScrollableFrame(self, height=400)
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # 初始加载已有文件
        for f in getattr(self.program, self.program_attr):
            self._add_card(f)

    def _add_file(self):
        files = getattr(self.program, self.program_attr)
        if len(files) >= 10:
            from tkinter import messagebox
            messagebox.showwarning("提示", "最多支持 10 个文件")
            return
        default_prefix = f"{'FI' if self.is_input else 'FO'}{len(files)+1:02d}"
        default_name = f"{'KWFAC' if self.is_input else 'KWOUT'}{len(files)+1}"
        new_file = FileDefinition(
            name=default_name,
            physical_name=f"SYS{len(files)+1:03d}-DA-DK-S",
            file_status=f"W-FS-{default_name}",
            copybook_name="",
            prefix=default_prefix,
            is_input=self.is_input,
        )
        files.append(new_file)
        self._add_card(new_file)

    def _add_card(self, file_def: FileDefinition):
        card = FileCard(self.scroll, file_def, on_delete=lambda fd=file_def: self._remove_file(fd))
        card.pack(fill="x", padx=5, pady=5)
        self.cards.append(card)

    def _remove_file(self, file_def: FileDefinition):
        files = getattr(self.program, self.program_attr)
        if file_def in files:
            files.remove(file_def)
        for card in self.cards:
            if card.file_def is file_def:
                card.destroy()
                self.cards.remove(card)
                break

    def save_all(self):
        for card in self.cards:
            card.save_to_model()


class CustomVariableEditor(ctk.CTkFrame):
    """自定义变量编辑器。"""

    def __init__(self, master, program: CobolProgram, on_change: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.program = program
        self.on_change = on_change
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="自定义变量", font=("Microsoft YaHei", 13, "bold")).pack(pady=5)

        # 输入表单
        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(form, text="阶数").grid(row=0, column=0, padx=5, pady=2)
        self.ent_level = ctk.CTkEntry(form, width=60)
        self.ent_level.insert(0, "05")
        self.ent_level.grid(row=0, column=1, padx=5, pady=2)

        ctk.CTkLabel(form, text="变量名").grid(row=0, column=2, padx=5, pady=2)
        self.ent_name = ctk.CTkEntry(form, width=150)
        self.ent_name.grid(row=0, column=3, padx=5, pady=2)

        ctk.CTkLabel(form, text="数据类型").grid(row=1, column=0, padx=5, pady=2)
        self.cmb_type = ctk.CTkComboBox(form, values=["X(文本)", "9(数字)", "S9(数字)"], width=120)
        self.cmb_type.set("X(文本)")
        self.cmb_type.grid(row=1, column=1, padx=5, pady=2)

        ctk.CTkLabel(form, text="长度").grid(row=1, column=2, padx=5, pady=2)
        self.ent_len = ctk.CTkEntry(form, width=80)
        self.ent_len.insert(0, "20")
        self.ent_len.grid(row=1, column=3, padx=5, pady=2)

        ctk.CTkLabel(form, text="初始值").grid(row=2, column=0, padx=5, pady=2)
        self.ent_init = ctk.CTkEntry(form, width=150)
        self.ent_init.grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(form, text="所属区域").grid(row=2, column=3, padx=5, pady=2)
        self.cmb_section = ctk.CTkComboBox(form, values=["WORKING-STORAGE", "LINKAGE", "LOCAL-STORAGE"], width=140)
        self.cmb_section.set("WORKING-STORAGE")
        self.cmb_section.grid(row=2, column=4, padx=5, pady=2)

        ctk.CTkButton(self, text="追加变量", command=self._add_variable).pack(pady=5)

        # 变量列表
        self.var_scroll = ctk.CTkScrollableFrame(self, height=200)
        self.var_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self._render_list()

    def _pic_from_inputs(self) -> str:
        level = self.ent_level.get().strip()
        vtype = self.cmb_type.get().strip().upper()
        # 归一化带说明的类型，如“X(文本)” -> “X”
        if "(" in vtype:
            vtype = vtype.split("(")[0]
        length = self.ent_len.get().strip()
        if level in ("77", "88"):
            return vtype
        if vtype in ("X", "9", "S9"):
            return f"{vtype}({length})"
        return vtype

    def _add_variable(self):
        name = self.ent_name.get().strip()
        if not name:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请输入变量名")
            return
        var = CustomVariable(
            level=self.ent_level.get().strip(),
            name=name,
            var_type=self.cmb_type.get().strip().upper(),
            length=self.ent_len.get().strip(),
            initial_value=self.ent_init.get().strip(),
            section=self.cmb_section.get().strip(),
        )
        self.program.custom_variables.append(var)
        self._render_list()
        if self.on_change:
            self.on_change()

    def _render_list(self):
        for w in self.var_scroll.winfo_children():
            w.destroy()

        headers = ["阶数", "变量名", "PIC/类型", "长度", "初始值", "区域", "操作"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self.var_scroll, text=h, font=("Microsoft YaHei", 9, "bold")).grid(row=0, column=col, padx=5, pady=2)

        for row, var in enumerate(self.program.custom_variables, start=1):
            ctk.CTkLabel(self.var_scroll, text=var.level).grid(row=row, column=0, padx=5, pady=1)
            ctk.CTkLabel(self.var_scroll, text=var.name).grid(row=row, column=1, padx=5, pady=1)
            ctk.CTkLabel(self.var_scroll, text=var.var_type).grid(row=row, column=2, padx=5, pady=1)
            ctk.CTkLabel(self.var_scroll, text=var.length).grid(row=row, column=3, padx=5, pady=1)
            ctk.CTkLabel(self.var_scroll, text=var.initial_value).grid(row=row, column=4, padx=5, pady=1)
            ctk.CTkLabel(self.var_scroll, text=var.section).grid(row=row, column=5, padx=5, pady=1)
            ctk.CTkButton(self.var_scroll, text="删除", width=50, command=lambda v=var: self._delete_variable(v)).grid(row=row, column=6, padx=5, pady=1)

    def _delete_variable(self, var: CustomVariable):
        self.program.custom_variables.remove(var)
        self._render_list()
        if self.on_change:
            self.on_change()


class DataPreviewFrame(ctk.CTkFrame):
    """DATA DIVISION 预览。"""

    def __init__(self, master, get_program: Callable, **kwargs):
        super().__init__(master, **kwargs)
        self.get_program = get_program
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="DATA DIVISION 预览", font=("Microsoft YaHei", 13, "bold")).pack(pady=5)
        self.text = ctk.CTkTextbox(self, font=("Consolas", 10), wrap="none")
        self.text.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh(self):
        from generator import generate_cobol
        prog = self.get_program()
        try:
            # 只生成 DATA DIVISION 部分比较麻烦，这里生成完整代码后截取
            full = generate_cobol(prog, inline_copybooks=True)
            # 截取 DATA DIVISION 到 WORKING-STORAGE 之前，或整个 DATA DIVISION
            start = full.find("DATA DIVISION.")
            end = full.find("LINKAGE SECTION.")
            if end == -1:
                end = full.find("PROCEDURE DIVISION.")
            preview = full[start:end] if start != -1 and end != -1 else full
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", preview)
        except Exception as e:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", f"生成预览失败: {e}")
