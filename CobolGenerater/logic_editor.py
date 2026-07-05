"""节点拖拽画布逻辑编辑器（基于 tkinter Canvas）。"""
import tkinter as tk
from tkinter import simpledialog, ttk
from typing import Callable, List, Optional

import customtkinter as ctk

from models import Condition, CobolProgram, EvaluateCase, LogicStep, MappingRule, Operand, Procedure


NODE_COLORS = {
    "IF": "#E3F2FD",
    "EVALUATE": "#E8F5E9",
    "COMPUTE": "#FFF3E0",
    "PERFORM": "#F3E5F5",
    "MOVE": "#E0F7FA",
    "INITIALIZE": "#FBE9E7",
    "CALL": "#ECEFF1",
    "SECTION": "#FFFDE7",
    "PARAGRAPH": "#FFFDE7",
}

NODE_TITLES = {
    "IF": "IF 判断",
    "EVALUATE": "EVALUATE 多分支",
    "COMPUTE": "COMPUTE 计算",
    "PERFORM": "PERFORM 循环",
    "MOVE": "MOVE 移送",
    "INITIALIZE": "INITIALIZE 初始化",
    "CALL": "CALL 子程序",
    "SECTION": "SECTION 节",
    "PARAGRAPH": "PARAGRAPH 段",
}

CONTAINER_TYPES = {"IF", "EVALUATE", "PERFORM"}


def _collect_operands(program: CobolProgram) -> list[str]:
    """收集当前程序中可作为操作数的字段/变量名（输入/输出字段 + 自定义变量）。"""
    opts = []
    for f in program.input_files:
        opts.extend([fld.full_name for fld in f.fields if fld.level > 1])
    for f in program.output_files:
        opts.extend([fld.full_name for fld in f.fields if fld.level > 1])
    opts.extend([v.name for v in program.custom_variables])
    return sorted(set(opts))


def _filter_numeric(text: str) -> str:
    """过滤字符串，仅保留数字和最多一个小数点。"""
    result = []
    dot_seen = False
    for ch in text:
        if ch.isdigit():
            result.append(ch)
        elif ch == "." and not dot_seen:
            result.append(ch)
            dot_seen = True
    return "".join(result)


def _is_numeric_literal(text: str) -> bool:
    """判断字符串是否只包含数字和最多一个小数点。"""
    if not text:
        return True
    if text.count(".") > 1:
        return False
    return all(ch.isdigit() or ch == "." for ch in text)


def _build_literal_editor(
    master: tk.Widget,
    parent: tk.Widget,
    operand: Operand,
    entry_width: int = 12,
) -> tuple[ttk.Combobox, tk.Entry, Callable[[], Operand]]:
    """在 parent 中创建字面量类型选择+值输入框，返回 (type_combo, entry, get_operand_fn)。"""
    is_literal = operand and operand.op_type == "LITERAL"
    lit_type = operand.literal_type if is_literal else "TEXT"
    val = operand.value if is_literal else ""

    type_combo = ttk.Combobox(parent, values=["数字", "文本"], state="readonly", width=6)
    type_combo.set("数字" if lit_type == "NUMERIC" else "文本")
    type_combo.pack(side="left", padx=(4, 0))

    entry = tk.Entry(parent, width=entry_width)
    entry.insert(0, val)
    entry.pack(side="left", padx=(4, 0))

    vcmd = master.register(lambda value, tc=type_combo: _is_numeric_literal(value) if tc.get() == "数字" else True)
    entry.config(validate="key", validatecommand=(vcmd, "%P"))

    def _on_type_change(event=None, entry=entry, type_combo=type_combo):
        if type_combo.get() == "数字":
            filtered = _filter_numeric(entry.get())
            entry.delete(0, tk.END)
            entry.insert(0, filtered)

    type_combo.bind("<<ComboboxSelected>>", _on_type_change)

    def _get_operand() -> Operand:
        lit_type = "NUMERIC" if type_combo.get() == "数字" else "TEXT"
        return Operand("LITERAL", entry.get().strip(), literal_type=lit_type)

    return type_combo, entry, _get_operand


def _compute_expr_summary(step: LogicStep) -> str:
    """返回 COMPUTE 表达式的可阅读摘要。"""
    operands = step.compute_operands
    operators = step.compute_operators
    if len(operands) < 2:
        return "?"
    parts = [operands[0].value if operands[0] else "?"]
    for i, op in enumerate(operators):
        if i + 1 >= len(operands):
            break
        parts.append(op)
        parts.append(operands[i + 1].value if operands[i + 1] else "?")
    return " ".join(parts)


def _cond_summary(c: Optional[Condition]) -> str:
    """返回单个条件的可阅读摘要。"""
    if not c:
        return ""
    left = c.left.value if c.left else "?"
    right = c.right.value if c.right else "?"
    return f"{left} {c.operator} {right}"


def _conditions_summary(conditions: List[Condition]) -> str:
    """返回多个条件的可阅读摘要（按 logical_op 连接）。"""
    if not conditions:
        return ""
    parts = []
    for i, c in enumerate(conditions):
        parts.append(_cond_summary(c))
        if i < len(conditions) - 1:
            parts.append(c.logical_op or "AND")
    return " ".join(parts)


def _mapping_summary(step: LogicStep) -> str:
    """返回 MOVE 节点字段映射的可阅读摘要。"""
    rules = step.mapping_rules
    if not rules:
        return "（空）"
    valid = [r for r in rules if r.source and r.target and r.source.value and r.target.value]
    if not valid:
        return "（空）"
    if len(valid) == 1:
        src = valid[0].source.value
        tgt = valid[0].target.value
        return f"{src} → {tgt}"
    return f"{len(valid)} 条映射"


class _NodeItem:
    """画布上的单个节点视图。"""

    def __init__(
        self,
        canvas: tk.Canvas,
        step: LogicStep,
        x: int,
        y: int,
        program: CobolProgram,
        parent: Optional["_NodeItem"] = None,
        on_select: Optional[Callable] = None,
        on_edit_children: Optional[Callable] = None,
    ):
        self.canvas = canvas
        self.step = step
        self.program = program
        self.parent = parent
        self.on_select = on_select
        self.on_edit_children = on_edit_children
        self.editor = self._find_editor()
        self.scale_factor = self.editor.scale_factor if self.editor else 1.0
        self.width = int(max(180, step.width) * self.scale_factor)
        self.height = int(max(70, step.height) * self.scale_factor)
        self.tag = f"node_{step.id}"

        self._draw()
        self._bind_events()

    def _draw(self):
        color = NODE_COLORS.get(self.step.step_type, "#FFFFFF")
        title = NODE_TITLES.get(self.step.step_type, self.step.step_type)
        s = self.scale_factor

        # 标题栏（通用）
        title_h = int(24 * s)
        self.rect = self.canvas.create_rectangle(
            0, 0, self.width, title_h,
            fill="#90A4AE", outline="#546E7A", width=1,
            tags=(self.tag, "node_rect"),
        )
        self.title_text = self.canvas.create_text(
            int(8 * s), title_h // 2, text=title, anchor="w",
            font=("Microsoft YaHei", max(6, int(10 * s)), "bold"),
            tags=(self.tag, "node_title"),
        )

        if self.step.step_type == "IF":
            self._draw_if_body(color)
        else:
            self._draw_normal_body(color)

        # 输入/输出端口（通用）
        port_r = max(3, int(5 * s))
        self.in_port = self.canvas.create_oval(
            self.width // 2 - port_r, -port_r, self.width // 2 + port_r, port_r,
            fill="#2196F3", outline="white", tags=(self.tag, "port"),
        )
        self.out_port = self.canvas.create_oval(
            self.width // 2 - port_r, self.height - port_r,
            self.width // 2 + port_r, self.height + port_r,
            fill="#2196F3", outline="white", tags=(self.tag, "port"),
        )

        # 容器节点：增加「编辑子步骤」按钮（使用唯一 tag 避免多节点共享绑定）
        if self.step.step_type in CONTAINER_TYPES and self.on_edit_children:
            self.edit_btn_tag = f"edit_btn_{self.step.id}"
            btn_left = self.width - int(50 * s)
            btn_top = int(2 * s)
            btn_right = self.width - int(2 * s)
            btn_bottom = int(22 * s)
            self.edit_btn = self.canvas.create_rectangle(
                btn_left, btn_top, btn_right, btn_bottom,
                fill="#64B5F6", outline="white", tags=(self.tag, self.edit_btn_tag),
            )
            self.edit_btn_text = self.canvas.create_text(
                (btn_left + btn_right) // 2, (btn_top + btn_bottom) // 2,
                text="编辑", fill="white",
                font=("Microsoft YaHei", max(6, int(8 * s))),
                tags=(self.tag, self.edit_btn_tag),
            )
            self.canvas.tag_bind(self.edit_btn_tag, "<Button-1>", lambda e: self.on_edit_children(self.step))

        cx, cy = int(self.step.x * s), int(self.step.y * s)
        self.canvas.move(self.tag, cx, cy)

    def _draw_normal_body(self, color: str):
        text = self._summary_text()
        s = self.scale_factor
        title_h = int(24 * s)
        self.body = self.canvas.create_rectangle(
            0, title_h, self.width, self.height,
            fill=color, outline="#546E7A", width=1,
            tags=(self.tag, "node_body"),
        )
        self.body_text = self.canvas.create_text(
            int(8 * s), title_h + int(8 * s), text=text, anchor="nw",
            width=self.width - int(16 * s),
            font=("Consolas", max(6, int(9 * s))),
            tags=(self.tag, "node_text"),
        )

    def _draw_if_body(self, color: str):
        """IF 节点：左右两列显示 THEN / ELSE，底部汇合到 END-IF。"""
        then_steps = self.step.then_body or []
        else_steps = self.step.else_body or []
        s = self.scale_factor
        line_height = max(12, int(18 * s))
        min_height = int(110 * s)
        self.width = int(260 * s)
        self.height = max(min_height, min_height + max(len(then_steps), len(else_steps)) * line_height)
        title_h = int(24 * s)

        self.body = self.canvas.create_rectangle(
            0, title_h, self.width, self.height,
            fill=color, outline="#546E7A", width=1,
            tags=(self.tag, "node_body"),
        )

        # 条件
        cond_text = f"IF {self._cond_text(self.step.conditions) or '条件未设置'}"
        self.body_text = self.canvas.create_text(
            self.width // 2, title_h + int(10 * s), text=cond_text, anchor="n",
            font=("Consolas", max(6, int(9 * s)), "bold"),
            width=self.width - int(16 * s),
            tags=(self.tag, "node_text"),
        )

        # THEN / ELSE 标签
        label_y = title_h + int(32 * s)
        self.canvas.create_text(
            self.width // 4, label_y, text="THEN", anchor="n",
            font=("Microsoft YaHei", max(6, int(8 * s)), "bold"), fill="#2E7D32",
            tags=(self.tag, "branch_label"),
        )
        self.canvas.create_text(
            self.width * 3 // 4, label_y, text="ELSE", anchor="n",
            font=("Microsoft YaHei", max(6, int(8 * s)), "bold"), fill="#C62828",
            tags=(self.tag, "branch_label"),
        )

        # 分隔线
        mid_x = self.width // 2
        self.canvas.create_line(
            mid_x, title_h + int(30 * s), mid_x, self.height - int(30 * s),
            fill="#90A4AE", dash=(3, 3), tags=(self.tag, "divider"),
        )

        # THEN 分支步骤
        y = title_h + int(52 * s)
        for step in then_steps:
            self.canvas.create_text(
                int(8 * s), y, text=self._step_summary(step), anchor="nw",
                width=mid_x - int(16 * s),
                font=("Consolas", max(6, int(8 * s))),
                tags=(self.tag, "then_step"),
            )
            y += line_height

        # ELSE 分支步骤
        y = title_h + int(52 * s)
        for step in else_steps:
            self.canvas.create_text(
                mid_x + int(8 * s), y, text=self._step_summary(step), anchor="nw",
                width=mid_x - int(16 * s),
                font=("Consolas", max(6, int(8 * s))),
                tags=(self.tag, "else_step"),
            )
            y += line_height

        # 分支汇合到 END-IF
        self.canvas.create_line(
            int(10 * s), self.height - int(24 * s),
            self.width - int(10 * s), self.height - int(24 * s),
            fill="#546E7A", width=1, tags=(self.tag, "endif_line"),
        )
        self.endif_text = self.canvas.create_text(
            self.width // 2, self.height - int(16 * s), text="END-IF", anchor="n",
            font=("Microsoft YaHei", max(6, int(8 * s)), "bold"), fill="#37474F",
            tags=(self.tag, "endif_text"),
        )

    def _step_summary(self, step: LogicStep) -> str:
        if step.step_type == "MOVE":
            return f"MOVE {_mapping_summary(step)}"
        if step.step_type == "COMPUTE":
            tgt = step.compute_target.value if step.compute_target else "?"
            return f"COMPUTE {tgt} = {_compute_expr_summary(step)}"
        if step.step_type == "INITIALIZE":
            return "INITIALIZE ..."
        if step.step_type == "CALL":
            return f"CALL {step.call_program}"
        if step.step_type == "CONTINUE":
            return "CONTINUE"
        if step.step_type == "IF":
            return f"IF {self._cond_text(step.conditions) or '...'}"
        return step.step_type

    def _summary_text(self) -> str:
        s = self.step
        if s.step_type == "IF":
            return self._cond_text(s.conditions) or "条件未设置"
        if s.step_type == "EVALUATE":
            return f"评估: {s.evaluate_subject.value if s.evaluate_subject else '?' }\n分支数: {len(s.evaluate_cases)}"
        if s.step_type == "COMPUTE":
            return f"{s.compute_target.value if s.compute_target else '?'} = {_compute_expr_summary(s)}"
        if s.step_type == "PERFORM":
            return f"PERFORM {s.perform_type}\n{s.perform_target or (s.perform_condition and self._cond_text(s.perform_condition)) or ''}"
        if s.step_type == "MOVE":
            return f"MOVE\n{_mapping_summary(s)}"
        if s.step_type == "INITIALIZE":
            return "INITIALIZE " + ", ".join(o.value for o in s.initialize_targets)
        if s.step_type == "CALL":
            return f"CALL '{s.call_program}'"
        if s.step_type == "SECTION":
            return s.label or "节未命名"
        return s.label or s.step_type

    def _cond_text(self, c) -> str:
        if isinstance(c, list):
            if not c:
                return ""
            parts = []
            for i, cond in enumerate(c):
                parts.append(self._cond_text(cond))
                if i < len(c) - 1:
                    parts.append(cond.logical_op or "AND")
            return " ".join(parts)
        if not c:
            return ""
        left = c.left.value if c.left else "?"
        right = c.right.value if c.right else "?"
        return f"{left} {c.operator} {right}"

    def _bind_events(self):
        self.canvas.tag_bind(self.tag, "<Button-1>", self._on_press)
        self.canvas.tag_bind(self.tag, "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._on_release)
        self.canvas.tag_bind(self.tag, "<Double-Button-1>", self._on_double)
        # 编辑按钮的绑定在 _draw 中随节点重绘重新创建

    def _on_press(self, event):
        self._last_x = event.x
        self._last_y = event.y
        if self.on_select:
            self.on_select(self)

    def _on_drag(self, event):
        dx = event.x - self._last_x
        dy = event.y - self._last_y
        self._last_x = event.x
        self._last_y = event.y
        # 鼠标位移是画布像素，按缩放比例换算回逻辑坐标
        scale = self.scale_factor
        self.step.x += dx / scale
        self.step.y += dy / scale
        self.canvas.move(self.tag, dx, dy)
        # 通知父编辑器重绘连线
        if self.parent is None:
            editor = self.editor
            if editor:
                editor._draw_connections()

    def _on_release(self, event):
        editor = self.editor
        if editor:
            editor._draw_connections()

    def _find_editor(self):
        """向上查找 NodeEditor 实例。"""
        parent = self.canvas.master
        while parent is not None:
            if isinstance(parent, NodeEditor):
                return parent
            parent = parent.master
        return None

    def _on_double(self, event):
        self.edit_properties()

    def edit_properties(self):
        if self.step.step_type == "IF":
            dialog = _EditIfDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "EVALUATE":
            dialog = _EditEvaluateDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "COMPUTE":
            dialog = _EditComputeDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "PERFORM":
            dialog = _EditPerformDialog(self.canvas, self.step)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "MOVE":
            dialog = _EditMoveDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "INITIALIZE":
            dialog = _EditInitializeDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type == "CALL":
            dialog = _EditCallDialog(self.canvas, self.step, self.program)
            self.canvas.wait_window(dialog)
        elif self.step.step_type in ("SECTION", "PARAGRAPH"):
            name = simpledialog.askstring("名称", "段落/节名:", initialvalue=self.step.label)
            if name:
                self.step.label = name
        self.refresh_text()
        # 通知外层编辑器刷新 COBOL 预览
        editor = self._find_editor()
        if editor and editor.on_change:
            editor.on_change()

    def refresh_text(self):
        if self.step.step_type == "IF":
            # IF 节点尺寸会随子步骤变化，直接重绘
            self.redraw()
        else:
            self.canvas.itemconfig(self.body_text, text=self._summary_text())

    def redraw(self):
        """删除并重新绘制该节点的所有画布元素。"""
        self.canvas.delete(self.tag)
        self._draw()

    def set_color(self, color: str):
        self.canvas.itemconfig(self.body, fill=color)


class _BaseEditDialog(tk.Toplevel):
    def __init__(self, parent, step: LogicStep):
        super().__init__(parent)
        self.step = step
        self.title(f"编辑 {step.step_type}")
        self.geometry("420x300")
        self.transient(parent)
        self.grab_set()

    def _operand_frame(self, parent, label_text: str, default: str = "") -> tk.Entry:
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text=label_text, width=10, anchor="w").pack(side="left")
        ent = tk.Entry(frame)
        ent.insert(0, default)
        ent.pack(side="left", fill="x", expand=True)
        return ent

    def _combo_frame(self, parent, label_text: str, values: list[str], default: str = "") -> ttk.Combobox:
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text=label_text, width=10, anchor="w").pack(side="left")
        cmb = ttk.Combobox(frame, values=values, state="readonly", width=30)
        if default in values:
            cmb.set(default)
        cmb.pack(side="left", fill="x", expand=True)
        return cmb


class _EditIfDialog(_BaseEditDialog):
    """IF 条件编辑对话框：支持多个条件以 AND/OR 连接。"""

    LOGICAL_OPS = ["AND", "OR"]

    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent, step)
        self.options = _collect_operands(program)
        self.geometry("520x480")

        # 本地副本
        self.conditions: list[Condition] = []
        for c in step.conditions if step.conditions else [Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))]:
            self.conditions.append(Condition(
                Operand(c.left.op_type, c.left.value, literal_type=c.left.literal_type) if c.left else Operand("FIELD", ""),
                c.operator,
                Operand(c.right.op_type, c.right.value, literal_type=c.right.literal_type) if c.right else Operand("LITERAL", ""),
                c.logical_op,
            ))

        tk.Label(self, text="条件列表（支持 AND / OR）:", anchor="w").pack(fill="x", padx=10, pady=(10, 0))

        # 条件区域（可滚动）
        cond_outer = tk.Frame(self)
        cond_outer.pack(fill="both", expand=True, padx=10, pady=5)
        self.cond_canvas = tk.Canvas(cond_outer, highlightthickness=0)
        scrollbar = tk.Scrollbar(cond_outer, command=self.cond_canvas.yview)
        self.cond_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.cond_canvas.pack(side="left", fill="both", expand=True)
        self.cond_frame = tk.Frame(self.cond_canvas)
        self.cond_canvas.create_window((0, 0), window=self.cond_frame, anchor="nw", width=self.cond_canvas.winfo_width())
        self.cond_canvas.bind("<Configure>", lambda e: self.cond_canvas.itemconfig(self.cond_canvas.find_withtag("all")[0], width=e.width))

        self.row_widgets: list[dict] = []
        self._render_conditions()

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="+ 添加条件", command=self._add_condition).pack(side="left")
        tk.Button(btn_frame, text="确定", command=self._ok).pack(side="right")

    def _render_conditions(self):
        for child in self.cond_frame.winfo_children():
            child.destroy()
        self.row_widgets.clear()

        for i, cond in enumerate(self.conditions):
            row = tk.Frame(self.cond_frame)
            row.pack(fill="x", pady=3)

            left_cmb = ttk.Combobox(row, values=self.options, state="readonly", width=14)
            left_cmb.set(cond.left.value if cond.left else "")
            left_cmb.pack(side="left")

            op_ent = tk.Entry(row, width=5)
            op_ent.insert(0, cond.operator)
            op_ent.pack(side="left", padx=4)

            right_ent = tk.Entry(row, width=14)
            right_ent.insert(0, cond.right.value if cond.right else "")
            right_ent.pack(side="left", padx=4)

            log_cmb = None
            if i < len(self.conditions) - 1:
                log_cmb = ttk.Combobox(row, values=self.LOGICAL_OPS, state="readonly", width=6)
                log_cmb.set(cond.logical_op if cond.logical_op else "AND")
                log_cmb.pack(side="left", padx=4)

            tk.Button(row, text="删除", command=lambda idx=i: self._delete_condition(idx)).pack(side="left", padx=4)

            self.row_widgets.append({
                "left": left_cmb,
                "left_var": left_var if true_mode else None,
                "op": op_ent,
                "right": right_ent,
                "logical_op": log_cmb,
                "logical_op_var": log_var if i < len(case.conditions) - 1 else None,
            })

        self.cond_frame.update_idletasks()
        bbox = self.cond_canvas.bbox("all")
        self.cond_canvas.config(scrollregion=bbox if bbox else (0, 0, 0, 0))

    def _sync_conditions_from_ui(self):
        """把当前条件编辑区内容同步回 self.conditions。"""
        synced = []
        for widgets in self.row_widgets:
            cond = Condition(
                Operand("FIELD", widgets["left"].get()),
                widgets["op"].get(),
                Operand("LITERAL", widgets["right"].get()),
                widgets["logical_op"].get() if widgets["logical_op"] else "",
            )
            synced.append(cond)
        self.conditions = synced

    def _add_condition(self):
        self._sync_conditions_from_ui()
        self.conditions.append(Condition(Operand("FIELD", ""), "=", Operand("LITERAL", "")))
        self._render_conditions()

    def _delete_condition(self, idx: int):
        if len(self.conditions) <= 1:
            return
        self._sync_conditions_from_ui()
        del self.conditions[idx]
        # 删除后重新调整最后一个条件的 logical_op
        if self.conditions:
            self.conditions[-1].logical_op = ""
        self._render_conditions()

    def _ok(self):
        saved = []
        for i, widgets in enumerate(self.row_widgets):
            cond = Condition(
                Operand("FIELD", widgets["left"].get()),
                widgets["op"].get(),
                Operand("LITERAL", widgets["right"].get()),
                widgets["logical_op"].get() if widgets["logical_op"] else "",
            )
            saved.append(cond)
        self.step.conditions = saved
        self.destroy()


class _EditEvaluateDialog(_BaseEditDialog):
    """EVALUATE 分支管理对话框：支持目标/TRUE 模式、多条件 AND/OR、增删改分支。"""

    SUBJECT_MODES = ["目标", "TRUE"]
    LOGICAL_OPS_TARGET = ["AND"]      # 目标模式生成 COBOL ALSO
    LOGICAL_OPS_TRUE = ["AND", "OR"]  # TRUE 模式生成 AND/OR

    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent, step)
        self.program = program
        self.options = _collect_operands(program) if program else []
        self.geometry("560x640")

        # ---------- 评估对象模式 ----------
        mode_frame = tk.Frame(self)
        mode_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(mode_frame, text="评估对象:", width=10, anchor="w").pack(side="left")
        self.cmb_subject_mode = ttk.Combobox(
            mode_frame, values=self.SUBJECT_MODES, state="readonly", width=10
        )
        is_true_mode = step.evaluate_subject and step.evaluate_subject.op_type == "TRUE"
        self.cmb_subject_mode.set("TRUE" if is_true_mode else "目标")
        self.cmb_subject_mode.pack(side="left", padx=4)
        self.cmb_subject_mode.bind("<<ComboboxSelected>>", self._on_subject_mode_change)

        subj_val = step.evaluate_subject.value if step.evaluate_subject and not is_true_mode else ""
        self.cmb_subject_target = ttk.Combobox(
            mode_frame, values=self.options, state="readonly", width=24
        )
        self.cmb_subject_target.set(subj_val)
        self.cmb_subject_target.pack(side="left", padx=4)

        # ---------- 分支列表 ----------
        tk.Label(self, text="分支列表:", anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(list_frame, font=("Consolas", 10))
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_case_select)

        # ---------- 分支条件编辑器（多条件，可滚动） ----------
        cond_outer = tk.LabelFrame(self, text="分支条件")
        cond_outer.pack(fill="x", padx=10, pady=5)
        self.cond_canvas = tk.Canvas(cond_outer, height=150, highlightthickness=0)
        cond_scroll = tk.Scrollbar(cond_outer, command=self.cond_canvas.yview)
        self.cond_canvas.configure(yscrollcommand=cond_scroll.set)
        cond_scroll.pack(side="right", fill="y")
        self.cond_canvas.pack(side="left", fill="both", expand=True)
        self.cond_rows_frame = tk.Frame(self.cond_canvas)
        self._cond_window = self.cond_canvas.create_window(
            (0, 0), window=self.cond_rows_frame, anchor="nw"
        )
        self.cond_canvas.bind("<Configure>", self._on_cond_canvas_configure)

        self.row_widgets: list[dict] = []

        cond_btn_frame = tk.Frame(self)
        cond_btn_frame.pack(fill="x", padx=10, pady=(0, 5))
        tk.Button(cond_btn_frame, text="+ 添加条件", command=self._add_condition).pack(side="left")
        self.chk_other_var = tk.BooleanVar()
        tk.Checkbutton(
            cond_btn_frame, text="OTHER", variable=self.chk_other_var,
            command=self._on_other_toggle,
        ).pack(side="left", padx=(20, 0))

        # ---------- 分支管理按钮 ----------
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="添加分支", command=self._add_case).pack(side="left", padx=2)
        tk.Button(btn_frame, text="添加 OTHER", command=self._add_other).pack(side="left", padx=2)
        tk.Button(btn_frame, text="删除", command=self._delete_case).pack(side="left", padx=2)
        tk.Button(btn_frame, text="上移", command=self._move_up).pack(side="left", padx=2)
        tk.Button(btn_frame, text="下移", command=self._move_down).pack(side="left", padx=2)
        tk.Button(btn_frame, text="编辑分支", command=self._edit_branch).pack(side="left", padx=(15, 2))

        tk.Button(self, text="确定", command=self._ok).pack(pady=10)

        # 本地副本
        self.cases: list[EvaluateCase] = []
        self._case_bodies: list[list[LogicStep]] = []
        for case in step.evaluate_cases:
            copied_conditions = [
                Condition(
                    Operand(c.left.op_type, c.left.value, literal_type=c.left.literal_type) if c.left else Operand("FIELD", ""),
                    c.operator,
                    Operand(c.right.op_type, c.right.value, literal_type=c.right.literal_type) if c.right else Operand("LITERAL", ""),
                    c.logical_op,
                )
                for c in case.conditions
            ]
            self.cases.append(EvaluateCase(conditions=copied_conditions, label=case.label))
            self._case_bodies.append(list(case.body))
        if not self.cases:
            self.cases.append(EvaluateCase(
                conditions=[Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))]
            ))
            self._case_bodies.append([])

        self._on_subject_mode_change()
        self._refresh_list()
        self.listbox.selection_set(0)
        self._on_case_select()

    def _is_true_mode(self) -> bool:
        return self.cmb_subject_mode.get() == "TRUE"

    def _on_subject_mode_change(self, event=None):
        self._sync_conditions_from_ui()
        if self._is_true_mode():
            self.cmb_subject_target.configure(state="disabled")
        else:
            self.cmb_subject_target.configure(state="readonly")
        self._render_conditions()

    def _on_cond_canvas_configure(self, event=None):
        self.cond_canvas.itemconfig(self._cond_window, width=event.width)

    @staticmethod
    def _case_summary(case: EvaluateCase, true_mode: bool = False) -> str:
        if not case.conditions:
            return "OTHER"
        if true_mode:
            return _conditions_summary(case.conditions)
        # 目标模式只显示值
        return " ALSO ".join(c.right.value if c.right else "?" for c in case.conditions)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        true_mode = self._is_true_mode()
        for case in self.cases:
            self.listbox.insert(tk.END, self._case_summary(case, true_mode))

    def _selected_index(self) -> Optional[int]:
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def _on_case_select(self, event=None):
        idx = self._selected_index()
        if idx is None:
            return
        case = self.cases[idx]
        is_other = not case.conditions
        self.chk_other_var.set(is_other)
        self._render_conditions()

    def _render_conditions(self):
        for child in self.cond_rows_frame.winfo_children():
            child.destroy()
        self.row_widgets.clear()

        idx = self._selected_index()
        if idx is None:
            return
        case = self.cases[idx]
        true_mode = self._is_true_mode()

        for i, cond in enumerate(case.conditions):
            row = tk.Frame(self.cond_rows_frame)
            row.pack(fill="x", pady=3)

            if true_mode:
                left_var = tk.StringVar()
                left_var.set(cond.left.value if cond.left else "")
                left_cmb = ttk.Combobox(row, values=self.options, state="readonly", width=14, textvariable=left_var)
                left_cmb.pack(side="left")
                left_var.trace_add("write", lambda *args: self._sync_conditions_from_ui())

                op_ent = tk.Entry(row, width=5)
                op_ent.insert(0, cond.operator)
                op_ent.pack(side="left", padx=4)
                op_ent.bind("<KeyRelease>", lambda e: self._sync_conditions_from_ui())
            else:
                left_cmb = None
                op_ent = None

            right_ent = tk.Entry(row, width=16)
            right_ent.insert(0, cond.right.value if cond.right else "")
            right_ent.pack(side="left", padx=4)
            right_ent.bind("<KeyRelease>", lambda e: self._sync_conditions_from_ui())

            log_ops = self.LOGICAL_OPS_TRUE if true_mode else self.LOGICAL_OPS_TARGET
            log_cmb = None
            if i < len(case.conditions) - 1:
                log_var = tk.StringVar()
                log_var.set(cond.logical_op if cond.logical_op else "AND")
                log_cmb = ttk.Combobox(row, values=log_ops, state="readonly", width=6, textvariable=log_var)
                log_cmb.pack(side="left", padx=4)
                log_var.trace_add("write", lambda *args: self._sync_conditions_from_ui())

            tk.Button(row, text="删除", command=lambda ci=i: self._delete_condition(ci)).pack(side="left", padx=4)

            self.row_widgets.append({
                "left": left_cmb,
                "left_var": left_var if true_mode else None,
                "op": op_ent,
                "right": right_ent,
                "logical_op": log_cmb,
                "logical_op_var": log_var if i < len(case.conditions) - 1 else None,
            })

        self.cond_rows_frame.update_idletasks()
        bbox = self.cond_canvas.bbox("all")
        self.cond_canvas.config(scrollregion=bbox if bbox else (0, 0, 0, 0))

    def _sync_conditions_from_ui(self):
        """把当前条件编辑区内容写回选中的 case。"""
        idx = self._selected_index()
        if idx is None or self.chk_other_var.get():
            return
        true_mode = self._is_true_mode()
        saved = []
        for widgets in self.row_widgets:
            left_val = widgets["left_var"].get() if widgets.get("left_var") else (widgets["left"].get() if widgets["left"] else "")
            op_val = widgets["op"].get() if true_mode and widgets["op"] else "="
            right_val = widgets["right"].get()
            log_val = widgets["logical_op_var"].get() if widgets.get("logical_op_var") else (widgets["logical_op"].get() if widgets["logical_op"] else "")
            cond = Condition(
                Operand("FIELD", left_val),
                op_val,
                Operand("LITERAL", right_val),
                log_val,
            )
            saved.append(cond)
        self.cases[idx].conditions = saved
        self._refresh_list()
        self.listbox.selection_set(idx)

    def _add_condition(self):
        self._sync_conditions_from_ui()
        idx = self._selected_index()
        if idx is None:
            return
        case = self.cases[idx]
        if not case.conditions:
            case.conditions = [Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))]
        else:
            case.conditions.append(Condition(Operand("FIELD", ""), "=", Operand("LITERAL", "")))
        self.chk_other_var.set(False)
        self._render_conditions()

    def _delete_condition(self, cond_idx: int):
        self._sync_conditions_from_ui()
        idx = self._selected_index()
        if idx is None:
            return
        case = self.cases[idx]
        if len(case.conditions) <= 1:
            return
        del case.conditions[cond_idx]
        if case.conditions:
            case.conditions[-1].logical_op = ""
        self._render_conditions()

    def _on_other_toggle(self):
        idx = self._selected_index()
        if idx is None:
            return
        case = self.cases[idx]
        if self.chk_other_var.get():
            case.conditions = []
        else:
            case.conditions = [Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))]
        self._render_conditions()
        self._refresh_list()
        self.listbox.selection_set(idx)

    def _add_case(self):
        self.cases.append(EvaluateCase(
            conditions=[Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))],
        ))
        self._case_bodies.append([])
        self._refresh_list()
        self.listbox.selection_set(len(self.cases) - 1)
        self._on_case_select()

    def _add_other(self):
        self.cases.append(EvaluateCase(conditions=[]))
        self._case_bodies.append([])
        self._refresh_list()
        self.listbox.selection_set(len(self.cases) - 1)
        self._on_case_select()

    def _delete_case(self):
        idx = self._selected_index()
        if idx is None:
            return
        del self.cases[idx]
        del self._case_bodies[idx]
        self._refresh_list()
        if self.cases:
            new_idx = min(idx, len(self.cases) - 1)
            self.listbox.selection_set(new_idx)
            self._on_case_select()

    def _move_up(self):
        idx = self._selected_index()
        if idx and idx > 0:
            self.cases[idx], self.cases[idx - 1] = self.cases[idx - 1], self.cases[idx]
            self._case_bodies[idx], self._case_bodies[idx - 1] = self._case_bodies[idx - 1], self._case_bodies[idx]
            self._refresh_list()
            self.listbox.selection_set(idx - 1)
            self._on_case_select()

    def _move_down(self):
        idx = self._selected_index()
        if idx is not None and idx < len(self.cases) - 1:
            self.cases[idx], self.cases[idx + 1] = self.cases[idx + 1], self.cases[idx]
            self._case_bodies[idx], self._case_bodies[idx + 1] = self._case_bodies[idx + 1], self._case_bodies[idx]
            self._refresh_list()
            self.listbox.selection_set(idx + 1)
            self._on_case_select()

    def _edit_branch(self):
        """打开分支体编辑器（与 IF 分支一致的 NodeEditor 标签页）。"""
        self._sync_conditions_from_ui()
        idx = self._selected_index()
        if idx is None:
            return
        self._sync_cases_to_step()
        ContainerEditor(self, self.step, program=self.program)
        self.wait_window(self.children[-1])
        for i, case in enumerate(self.step.evaluate_cases):
            if i < len(self._case_bodies):
                self._case_bodies[i] = list(case.body)
        self._refresh_list()

    def _sync_cases_to_step(self):
        for case, body in zip(self.cases, self._case_bodies):
            case.body = body
        self.step.evaluate_cases = self.cases

    def _ok(self):
        self._sync_conditions_from_ui()
        if self._is_true_mode():
            self.step.evaluate_subject = Operand("TRUE", "TRUE")
        else:
            self.step.evaluate_subject = Operand("FIELD", self.cmb_subject_target.get())
        self._sync_cases_to_step()
        self.destroy()


class _EditComputeDialog(_BaseEditDialog):
    """COMPUTE 编辑对话框：target = 运算单元1 [运算符 运算单元2 ...]。"""

    LITERAL_OPTION = "<字面量>"
    OPERATORS = ["+", "-", "*", "/", "**"]

    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent, step)
        self.options = _collect_operands(program)
        self.geometry("560x520")

        # 在对话框内部维护一份可增删改的副本，点确定后再写回 step
        self.operands = self._normalize_operands(step.compute_operands)
        self.operators = self._normalize_operators(step.compute_operators, len(self.operands))

        tgt = step.compute_target.value if step.compute_target else ""
        self.cmb_target = self._combo_frame(self, "目标:", self.options, tgt)

        # 表达式区域（纵向列表，带垂直滚动条）
        tk.Label(self, text="表达式:", anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        self.expr_outer = tk.Frame(self)
        self.expr_outer.pack(fill="both", expand=True, padx=10, pady=5)
        self.expr_canvas = tk.Canvas(self.expr_outer, height=260, highlightthickness=0)
        self.expr_scroll = tk.Scrollbar(
            self.expr_outer, orient="vertical", command=self.expr_canvas.yview
        )
        self.expr_canvas.configure(yscrollcommand=self.expr_scroll.set)
        self.expr_scroll.pack(side="right", fill="y")
        self.expr_canvas.pack(side="left", fill="both", expand=True)
        self.expr_frame = tk.Frame(self.expr_canvas)
        self._expr_window = self.expr_canvas.create_window(
            (0, 0), window=self.expr_frame, anchor="nw", width=self.expr_canvas.winfo_width()
        )
        self.expr_canvas.bind("<Configure>", self._on_expr_canvas_configure)

        self.operand_frames: list[tuple[ttk.Combobox, tk.Entry]] = []
        self.operator_combos: list[ttk.Combobox] = []

        self._render_expression()

        # 底部按钮（紧凑）
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 5))
        tk.Button(btn_frame, text="+ 添加运算单元", command=self._add_operand_pair).pack(side="left")
        tk.Button(btn_frame, text="确定", command=self._ok).pack(side="right")

    @staticmethod
    def _normalize_operands(operands):
        if not operands or len(operands) < 2:
            return [Operand("FIELD", ""), Operand("FIELD", "")]
        return [Operand(o.op_type, o.value, literal_type=o.literal_type) for o in operands]

    @staticmethod
    def _normalize_operators(operators, operand_count):
        needed = max(1, operand_count - 1)
        if not operators:
            return ["+"] * needed
        ops = list(operators)
        if len(ops) > needed:
            ops = ops[:needed]
        while len(ops) < needed:
            ops.append("+")
        return ops

    def _on_expr_canvas_configure(self, event=None):
        """画布大小变化时，内部框架宽度同步。"""
        self.expr_canvas.itemconfig(self._expr_window, width=event.width)

    def _render_expression(self):
        """根据 self.operands / self.operators 重新绘制表达式控件。"""
        for child in self.expr_frame.winfo_children():
            child.destroy()
        self.operand_frames.clear()
        self.operator_combos.clear()

        # 第一行：运算单元 1
        self._create_operand_row(0)

        # 后续：运算符 + 运算单元
        for i in range(len(self.operators)):
            self._create_operator_row(i)

        self.expr_frame.update_idletasks()
        bbox = self.expr_canvas.bbox("all")
        self.expr_canvas.config(scrollregion=bbox if bbox else (0, 0, 0, 0))

    def _create_operand_row(self, idx: int):
        """创建单个运算单元行（标签 + 下拉框 + 字面量输入框）。"""
        frame = tk.Frame(self.expr_frame)
        frame.pack(fill="x", pady=3)

        label_text = "运算单元1" if idx == 0 else f"运算单元{idx + 1}"
        tk.Label(frame, text=label_text, width=10, anchor="w").pack(side="left")
        self._place_operand_widget(frame, idx)

    def _create_operator_row(self, idx: int):
        """创建运算符行：运算符 + 运算单元 + 删除按钮。"""
        frame = tk.Frame(self.expr_frame)
        frame.pack(fill="x", pady=3)

        tk.Label(frame, text=f"运算符{idx + 1}", width=10, anchor="w").pack(side="left")

        op = self.operators[idx] if idx < len(self.operators) else "+"
        cmb_op = ttk.Combobox(frame, values=self.OPERATORS, state="readonly", width=5)
        cmb_op.set(op)
        cmb_op.pack(side="left", padx=(0, 8))
        self.operator_combos.append(cmb_op)

        self._place_operand_widget(frame, idx + 1)

        tk.Button(frame, text="删除", command=lambda i=idx: self._delete_pair(i)).pack(side="left", padx=(8, 0))

    def _place_operand_widget(self, parent: tk.Widget, idx: int):
        """在父容器中放置一个运算单元下拉框及字面量编辑器。"""
        op = self.operands[idx] if idx < len(self.operands) else Operand("FIELD", "")
        is_literal = op and op.op_type == "LITERAL"

        cmb = ttk.Combobox(
            parent, values=[self.LITERAL_OPTION] + self.options,
            state="readonly", width=16,
        )
        cmb.set(self.LITERAL_OPTION if is_literal else (op.value if op else ""))
        cmb.pack(side="left")

        type_combo, entry, get_operand = _build_literal_editor(self, parent, op, entry_width=12)

        def on_change(event=None, cmb=cmb, type_combo=type_combo, entry=entry):
            is_lit = cmb.get() == self.LITERAL_OPTION
            state = "readonly" if is_lit else "disabled"
            type_combo.configure(state=state)
            entry.configure(state="normal" if is_lit else "disabled")
            if not is_lit:
                entry.delete(0, tk.END)

        cmb.bind("<<ComboboxSelected>>", on_change)
        on_change()  # 初始化状态
        self.operand_frames.append((cmb, get_operand))

    def _add_operand_pair(self):
        """在表达式末尾追加一个运算符和运算单元。"""
        self.operands.append(Operand("FIELD", ""))
        self.operators.append("+")
        self._render_expression()

    def _delete_pair(self, idx: int):
        """删除第 idx 个运算符及其后一个运算单元。"""
        if len(self.operands) <= 2:
            return
        del self.operators[idx]
        del self.operands[idx + 1]
        self._render_expression()


    def _ok(self):
        """把编辑结果写回 step。"""
        self.step.compute_target = Operand("FIELD", self.cmb_target.get())

        saved_operands = []
        for cmb, get_operand in self.operand_frames:
            if cmb.get() == self.LITERAL_OPTION:
                saved_operands.append(get_operand())
            else:
                saved_operands.append(Operand("FIELD", cmb.get()))
        self.step.compute_operands = saved_operands

        saved_operators = [cmb.get() for cmb in self.operator_combos]
        self.step.compute_operators = saved_operators
        self.destroy()


class _EditPerformDialog(_BaseEditDialog):
    def __init__(self, parent, step: LogicStep):
        super().__init__(parent, step)
        self.ptype = self._operand_frame(self, "类型:", step.perform_type)
        self.target = self._operand_frame(self, "目标/条件:", step.perform_target)
        tk.Button(self, text="确定", command=self._ok).pack(pady=15)

    def _ok(self):
        self.step.perform_type = self.ptype.get()
        self.step.perform_target = self.target.get()
        self.destroy()


class _EditMoveDialog(ctk.CTkToplevel):
    """MOVE 字段映射编辑器：把字段映射模块作为 MOVE 节点的编辑界面。"""

    PLACEHOLDER_OPTION = "<请选择>"
    LITERAL_OPTION = "<字面量>"

    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent)
        self.step = step
        self.program = program
        self.title("编辑 MOVE 字段映射")
        self.geometry("760x580")
        self.transient(parent)
        self.grab_set()

        # 本地副本：编辑时操作副本，确定后再写回 step
        self.rules: list[MappingRule] = [
            MappingRule(
                source=Operand(r.source.op_type, r.source.value, literal_type=r.source.literal_type) if r.source else Operand("FIELD", ""),
                target=Operand(r.target.op_type, r.target.value, literal_type=r.target.literal_type) if r.target else Operand("FIELD", ""),
            )
            for r in step.mapping_rules
        ]
        self._rows: list = []

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="MOVE 字段映射规则（源 → 目标）", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_frame, text="同名自动映射", command=self._auto_map).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="+ 添加映射", command=self._add_rule).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="确定", command=self._ok).pack(side="right", padx=5)

        # 映射规则列表
        self.scroll = ctk.CTkScrollableFrame(self, height=320)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)

        # 代码预览
        ctk.CTkLabel(self, text="MOVE 代码预览", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.preview = ctk.CTkTextbox(self, height=140, font=("Consolas", 10), wrap="none")
        self.preview.pack(fill="x", padx=10, pady=5)

    def _get_options(self) -> list[str]:
        opts = []
        for f in self.program.input_files:
            opts.extend([fld.full_name for fld in f.fields if fld.level > 1])
        for f in self.program.output_files:
            opts.extend([fld.full_name for fld in f.fields if fld.level > 1])
        opts.extend([v.name for v in self.program.custom_variables])
        return sorted(set(opts))

    def _source_options(self) -> list[str]:
        return [self.PLACEHOLDER_OPTION, self.LITERAL_OPTION] + self._get_options()

    def _target_options(self) -> list[str]:
        return [self.PLACEHOLDER_OPTION] + self._get_options()

    def _readonly_combo(self, master, values, width=220):
        return ctk.CTkComboBox(master, values=values, width=width, state="readonly")

    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._rows.clear()

        headers = ["源", "字面量值", "目标", "操作"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self.scroll, text=h, font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=col, padx=5, pady=5)

        for idx, rule in enumerate(self.rules, start=1):
            self._add_rule_row(idx, rule)

        self._refresh_preview()

    def _add_rule_row(self, row: int, rule: MappingRule):
        source_options = self._source_options()
        target_options = self._target_options()

        is_literal = rule.source and rule.source.op_type == "LITERAL"
        source_val = rule.source.value if rule.source else ""
        target_val = rule.target.value if rule.target else ""

        cmb_source = self._readonly_combo(self.scroll, source_options, 220)
        if is_literal:
            cmb_source.set(self.LITERAL_OPTION)
        elif source_val and source_val in source_options:
            cmb_source.set(source_val)
        else:
            cmb_source.set(self.PLACEHOLDER_OPTION)
        cmb_source.grid(row=row, column=0, padx=5, pady=2)

        ent_literal = ctk.CTkEntry(self.scroll, width=150)
        if is_literal:
            ent_literal.insert(0, source_val)

        def set_literal_visible(visible: bool):
            if visible:
                ent_literal.grid(row=row, column=1, padx=5, pady=2)
                ent_literal.configure(state="normal")
            else:
                ent_literal.grid_remove()
                ent_literal.delete(0, tk.END)
                ent_literal.configure(state="disabled")

        set_literal_visible(is_literal)

        cmb_target = self._readonly_combo(self.scroll, target_options, 220)
        if target_val and target_val in target_options:
            cmb_target.set(target_val)
        else:
            cmb_target.set(self.PLACEHOLDER_OPTION)
        cmb_target.grid(row=row, column=2, padx=5, pady=2)

        ctk.CTkButton(self.scroll, text="删除", width=60, command=lambda r=rule: self._delete_rule(r)).grid(row=row, column=3, padx=5, pady=2)

        def on_source_change(event=None):
            set_literal_visible(cmb_source.get() == self.LITERAL_OPTION)
            self._sync_rules()

        cmb_source.bind("<<ComboboxSelected>>", on_source_change)
        cmb_source.configure(command=on_source_change)
        cmb_target.configure(command=lambda x: self._sync_rules())
        ent_literal.bind("<KeyRelease>", lambda e: self._sync_rules())

        self._rows.append((rule, cmb_source, ent_literal, cmb_target))

    def _add_rule(self):
        new_rule = MappingRule(source=Operand("FIELD", ""), target=Operand("FIELD", ""))
        self.rules.append(new_rule)
        self._refresh()

    def _delete_rule(self, rule: MappingRule):
        if rule in self.rules:
            self.rules.remove(rule)
        self._refresh()

    def _sync_rules(self):
        for rule, cmb_source, ent_literal, cmb_target in self._rows:
            src = cmb_source.get()
            if src == self.LITERAL_OPTION:
                literal_val = ent_literal.get().strip()
                if literal_val.upper() in ("SPACE", "SPACES", "ZERO", "ZEROS"):
                    rule.source = Operand("LITERAL", literal_val.upper())
                else:
                    rule.source = Operand("LITERAL", literal_val)
            elif src == self.PLACEHOLDER_OPTION:
                rule.source = Operand("FIELD", "")
            else:
                rule.source = Operand("FIELD", src)

            tgt = cmb_target.get()
            if tgt == self.PLACEHOLDER_OPTION:
                rule.target = Operand("FIELD", "")
            else:
                rule.target = Operand("FIELD", tgt)
        self._refresh_preview()

    def _auto_map(self):
        out_fields = []
        for f in self.program.output_files:
            out_fields.extend([fld for fld in f.fields if fld.level > 1])

        for f in self.program.input_files:
            for inf in f.fields:
                if inf.level <= 1:
                    continue
                for ouf in out_fields:
                    if ouf.name == inf.name:
                        exists = any(
                            r.source and r.source.value and r.target and r.target.value
                            and r.source.value == inf.full_name and r.target.value == ouf.full_name
                            for r in self.rules
                        )
                        if not exists:
                            self.rules.append(MappingRule(
                                source=Operand("FIELD", inf.full_name),
                                target=Operand("FIELD", ouf.full_name),
                            ))
        self._refresh()

    def _refresh_preview(self):
        lines = []
        for rule in self.rules:
            if not rule.source or not rule.target:
                continue
            src = rule.source.value or ""
            tgt = rule.target.value or ""
            if not src or not tgt:
                continue
            if rule.source.op_type == "LITERAL":
                if src.upper() in ("SPACE", "SPACES", "ZERO", "ZEROS"):
                    src_disp = src.upper()
                else:
                    src_disp = f"'{src}'"
            else:
                src_disp = src
            lines.append(f"    MOVE {src_disp} TO {tgt}.")
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", "\n".join(lines) if lines else "（暂无有效映射规则）")

    def _ok(self):
        self._sync_rules()
        self.step.mapping_rules = self.rules
        self.destroy()


class _EditInitializeDialog(_BaseEditDialog):
    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent, step)
        self.options = _collect_operands(program)
        self.targets = [o.value for o in step.initialize_targets]
        self.geometry("420x400")
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="初始化目标列表", font=("Microsoft YaHei", 10, "bold")).pack(pady=5)

        add_frame = tk.Frame(self)
        add_frame.pack(fill="x", padx=10, pady=5)
        self.cmb_add = ttk.Combobox(add_frame, values=self.options, state="readonly", width=25)
        self.cmb_add.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(add_frame, text="添加", command=self._add_target).pack(side="left", padx=5)

        self.listbox = tk.Listbox(self, font=("Consolas", 10))
        self.listbox.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="删除", command=self._delete_target).pack(side="left", padx=5)
        tk.Button(btn_frame, text="确定", command=self._ok).pack(side="right", padx=5)

        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for t in self.targets:
            self.listbox.insert(tk.END, t)

    def _add_target(self):
        val = self.cmb_add.get()
        if val and val not in self.targets:
            self.targets.append(val)
            self._refresh_list()

    def _delete_target(self):
        sel = self.listbox.curselection()
        if sel:
            del self.targets[sel[0]]
            self._refresh_list()

    def _ok(self):
        self.step.initialize_targets = [Operand("FIELD", v) for v in self.targets]
        self.destroy()


class _EditCallDialog(_BaseEditDialog):
    def __init__(self, parent, step: LogicStep, program: CobolProgram):
        super().__init__(parent, step)
        self.options = _collect_operands(program)
        self.using_values = [o.value for o in step.call_using]
        self.geometry("420x400")
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)
        tk.Label(top, text="程序名:", width=10, anchor="w").pack(side="left")
        self.ent_prog = tk.Entry(top)
        self.ent_prog.insert(0, self.step.call_program)
        self.ent_prog.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(self, text="USING 参数列表", font=("Microsoft YaHei", 10, "bold")).pack(pady=5)

        add_frame = tk.Frame(self)
        add_frame.pack(fill="x", padx=10, pady=5)
        self.cmb_add = ttk.Combobox(add_frame, values=self.options, state="readonly", width=25)
        self.cmb_add.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(add_frame, text="添加", command=self._add_param).pack(side="left", padx=5)

        self.listbox = tk.Listbox(self, font=("Consolas", 10))
        self.listbox.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="删除", command=self._delete_param).pack(side="left", padx=5)
        tk.Button(btn_frame, text="确定", command=self._ok).pack(side="right", padx=5)

        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for t in self.using_values:
            self.listbox.insert(tk.END, t)

    def _add_param(self):
        val = self.cmb_add.get()
        if val and val not in self.using_values:
            self.using_values.append(val)
            self._refresh_list()

    def _delete_param(self):
        sel = self.listbox.curselection()
        if sel:
            del self.using_values[sel[0]]
            self._refresh_list()

    def _ok(self):
        self.step.call_program = self.ent_prog.get().strip()
        self.step.call_using = [Operand("FIELD", v) for v in self.using_values]
        self.destroy()


# ----------------------------------------------------------------------
# 子步骤列表编辑器（用于 IF/EVALUATE/PERFORM 内部）
# ----------------------------------------------------------------------
class StepListEditor(tk.Toplevel):
    """简单的子步骤列表编辑器。"""

    def __init__(self, parent, steps: List[LogicStep], title: str = "编辑子步骤"):
        super().__init__(parent)
        self.steps = steps
        self.title(title)
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=5, pady=5)
        for t in ["MOVE", "COMPUTE", "INITIALIZE", "CALL", "CONTINUE"]:
            tk.Button(toolbar, text=f"+{t}", command=lambda t=t: self._add_step(t)).pack(side="left", padx=2)

        self.listbox = tk.Listbox(self, font=("Consolas", 10))
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(btn_frame, text="编辑", command=self._edit_step).pack(side="left", padx=5)
        tk.Button(btn_frame, text="删除", command=self._delete_step).pack(side="left", padx=5)
        tk.Button(btn_frame, text="上移", command=self._move_up).pack(side="left", padx=5)
        tk.Button(btn_frame, text="下移", command=self._move_down).pack(side="left", padx=5)
        tk.Button(btn_frame, text="确定", command=self.destroy).pack(side="right", padx=5)

        self._refresh_list()

    def _summary(self, step: LogicStep) -> str:
        if step.step_type == "MOVE":
            return f"MOVE {_mapping_summary(step)}"
        if step.step_type == "COMPUTE":
            return f"COMPUTE {step.compute_target.value if step.compute_target else '?'} = {_compute_expr_summary(step)}"
        if step.step_type == "IF":
            return f"IF {_conditions_summary(step.conditions) or '...'}"
        if step.step_type == "INITIALIZE":
            return f"INITIALIZE {', '.join(o.value for o in step.initialize_targets)}"
        if step.step_type == "CALL":
            return f"CALL '{step.call_program}'"
        if step.step_type == "CONTINUE":
            return "CONTINUE"
        return step.step_type

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for step in self.steps:
            self.listbox.insert(tk.END, self._summary(step))

    def _add_step(self, step_type: str):
        import uuid
        step = LogicStep(id=str(uuid.uuid4())[:8], step_type=step_type)
        if step_type == "MOVE":
            step.mapping_rules = [MappingRule(source=Operand("FIELD", ""), target=Operand("FIELD", ""))]
        elif step_type == "IF":
            step.conditions = [Condition(Operand("FIELD", ""), "=", Operand("LITERAL", ""))]
        elif step_type == "COMPUTE":
            step.compute_target = Operand("FIELD", "")
            step.compute_operands = [Operand("FIELD", ""), Operand("FIELD", "")]
            step.compute_operators = ["+"]
        elif step_type == "INITIALIZE":
            step.initialize_targets = [Operand("FIELD", "")]
        elif step_type == "CALL":
            step.call_program = ""
        self.steps.append(step)
        self._refresh_list()

    def _edit_step(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        step = self.steps[sel[0]]
        if step.step_type == "MOVE":
            _EditMoveDialog(self, step)
        elif step.step_type == "COMPUTE":
            _EditComputeDialog(self, step)
        elif step.step_type == "INITIALIZE":
            _EditInitializeDialog(self, step)
        elif step.step_type == "CALL":
            _EditCallDialog(self, step)
        self.wait_window(self.children[-1])  # 等待对话框关闭
        self._refresh_list()

    def _delete_step(self):
        sel = self.listbox.curselection()
        if sel:
            del self.steps[sel[0]]
            self._refresh_list()

    def _move_up(self):
        sel = self.listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            self.steps[idx], self.steps[idx - 1] = self.steps[idx - 1], self.steps[idx]
            self._refresh_list()
            self.listbox.selection_set(idx - 1)

    def _move_down(self):
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.steps) - 1:
            idx = sel[0]
            self.steps[idx], self.steps[idx + 1] = self.steps[idx + 1], self.steps[idx]
            self._refresh_list()
            self.listbox.selection_set(idx + 1)


class ContainerEditor(tk.Toplevel):
    """编辑 IF / EVALUATE / PERFORM 容器节点的子步骤。"""

    def __init__(self, parent, step: LogicStep, program: Optional[CobolProgram] = None):
        super().__init__(parent)
        self.step = step
        self.program = program
        if self.program is None and isinstance(self.master, NodeEditor):
            self.program = self.master.program
        self.title(f"编辑 {step.step_type} 子步骤")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        if self.step.step_type == "IF":
            notebook = ttk.Notebook(self)
            notebook.pack(fill="both", expand=True, padx=5, pady=5)

            then_frame = tk.Frame(notebook)
            else_frame = tk.Frame(notebook)
            notebook.add(then_frame, text="THEN")
            notebook.add(else_frame, text="ELSE")

            # THEN / ELSE 分支使用独立 NodeEditor，可拖拽链接其他模块
            self.then_editor = NodeEditor(
                then_frame, self.step.then_body,
                program=self.program,
                on_change=self._on_branch_change,
            )
            self.then_editor.pack(fill="both", expand=True)
            self.else_editor = NodeEditor(
                else_frame, self.step.else_body,
                program=self.program,
                on_change=self._on_branch_change,
            )
            self.else_editor.pack(fill="both", expand=True)

        elif self.step.step_type == "PERFORM":
            tk.Label(self, text=f"循环类型: {self.step.perform_type}").pack(pady=5)
            StepListEditor(self, self.step.perform_body, "循环体").pack(fill="both", expand=True, padx=5, pady=5)

        elif self.step.step_type == "EVALUATE":
            notebook = ttk.Notebook(self)
            notebook.pack(fill="both", expand=True, padx=5, pady=5)

            self.case_editors: list[NodeEditor] = []
            for idx, case in enumerate(self.step.evaluate_cases):
                tab_frame = tk.Frame(notebook)
                title = self._evaluate_case_title(case, idx)
                notebook.add(tab_frame, text=title)
                editor = NodeEditor(
                    tab_frame, case.body,
                    program=self.program,
                    on_change=self._on_branch_change,
                )
                editor.pack(fill="both", expand=True)
                self.case_editors.append(editor)

        tk.Button(self, text="确定", command=self.destroy).pack(pady=10)

    @staticmethod
    def _evaluate_case_title(case: EvaluateCase, idx: int) -> str:
        if not case.conditions:
            return "OTHER"
        summary = _conditions_summary(case.conditions)
        return summary[:30] + "..." if len(summary) > 30 else summary

    def _on_branch_change(self):
        """分支内节点变更时通知外层主编辑器刷新预览。"""
        master = self.master
        if master and callable(getattr(master, "on_change", None)):
            master.on_change()


# ----------------------------------------------------------------------
# PROC 列表（左侧导航）
# ----------------------------------------------------------------------
class ProcedureListFrame(ctk.CTkFrame):
    """左侧 PROC 列表：增删改查、排序、选中切换。"""

    def __init__(
        self,
        master,
        program: CobolProgram,
        on_select: Optional[Callable[[Procedure], None]] = None,
        on_change: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.program = program
        self.on_select = on_select
        self.on_change = on_change
        self._selected: Optional[Procedure] = None
        self._buttons: list[tuple[Procedure, ctk.CTkButton]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="PROC 列表", font=("Microsoft YaHei", 12, "bold")).pack(pady=5)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(btn_frame, text="+", width=30, command=self._add_proc).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="-", width=30, command=self._delete_proc).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="↑", width=30, command=self._move_up).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="↓", width=30, command=self._move_down).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="重命名", command=self._rename_proc).pack(side="left", padx=5)

        self.list_frame = ctk.CTkScrollableFrame(self, height=300)
        self.list_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._buttons.clear()

        for proc in self.program.procedures:
            display = f"{proc.name}\n({proc.title or '无标题'})" if proc.title else proc.name
            btn = ctk.CTkButton(
                self.list_frame,
                text=display,
                anchor="w",
                command=lambda p=proc: self._select_proc(p),
            )
            btn.pack(fill="x", pady=2)
            self._buttons.append((proc, btn))

        if self._selected not in self.program.procedures:
            self._selected = self.program.procedures[0] if self.program.procedures else None
        self._highlight()

    def _highlight(self):
        selected_color = "#2196F3"
        default_color = ["#3B8ED0", "#1F6AA5"]
        for proc, btn in self._buttons:
            btn.configure(fg_color=selected_color if proc == self._selected else default_color)

    def _select_proc(self, proc: Procedure):
        self._selected = proc
        self._highlight()
        if self.on_select:
            self.on_select(proc)

    def _add_proc(self):
        import uuid
        idx = len(self.program.procedures) + 1
        proc = Procedure(
            id=str(uuid.uuid4())[:8],
            name=f"PROC-{idx:02d}",
            title=f"处理{idx}",
            call_point="LOOP",
        )
        self.program.procedures.append(proc)
        self.refresh()
        self._select_proc(proc)
        if self.on_change:
            self.on_change()

    def _delete_proc(self):
        if self._selected and self._selected in self.program.procedures:
            self.program.procedures.remove(self._selected)
            self._selected = None
            self.refresh()
            if self.on_change:
                self.on_change()

    def _move_up(self):
        if not self._selected:
            return
        idx = self.program.procedures.index(self._selected)
        if idx > 0:
            self.program.procedures[idx], self.program.procedures[idx - 1] = (
                self.program.procedures[idx - 1], self.program.procedures[idx]
            )
            self.refresh()
            if self.on_change:
                self.on_change()

    def _move_down(self):
        if not self._selected:
            return
        idx = self.program.procedures.index(self._selected)
        if idx < len(self.program.procedures) - 1:
            self.program.procedures[idx], self.program.procedures[idx + 1] = (
                self.program.procedures[idx + 1], self.program.procedures[idx]
            )
            self.refresh()
            if self.on_change:
                self.on_change()

    def _rename_proc(self):
        if not self._selected:
            return
        name = simpledialog.askstring("重命名 PROC", "新名称:", initialvalue=self._selected.name)
        if name:
            self._selected.name = name.strip().upper().replace(" ", "-")
            self.refresh()
            if self.on_change:
                self.on_change()

    def get_selected(self) -> Optional[Procedure]:
        return self._selected


# ----------------------------------------------------------------------
# 主编辑器
# ----------------------------------------------------------------------
class NodeEditor(tk.Frame):
    """节点逻辑编辑器主控件。"""

    # 画布逻辑尺寸（逻辑坐标）
    CANVAS_LOGICAL_WIDTH = 2000
    CANVAS_LOGICAL_HEIGHT = 2000

    def __init__(
        self,
        master,
        steps: List[LogicStep],
        program: Optional[CobolProgram] = None,
        on_change: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.steps = steps
        self.program = program
        self.on_change = on_change
        self._node_items: dict[str, _NodeItem] = {}
        self._selected: Optional[_NodeItem] = None
        self.scale_factor = 1.0

        self._build_toolbar()
        self._build_canvas()
        self._render_steps()

    def _build_toolbar(self):
        toolbar = tk.Frame(self, bg="#F5F5F5")
        toolbar.pack(fill="x", padx=5, pady=5)

        types = ["IF", "EVALUATE", "COMPUTE", "PERFORM", "MOVE", "INITIALIZE", "CALL", "SECTION"]
        for t in types:
            btn = tk.Button(toolbar, text=t, command=lambda t=t: self._add_node(t))
            btn.pack(side="left", padx=2)

        tk.Button(toolbar, text="删除", command=self._delete_selected).pack(side="left", padx=10)

        tk.Label(toolbar, text="缩放:", bg="#F5F5F5").pack(side="left", padx=(15, 2))
        tk.Button(toolbar, text="-", width=2, command=self._zoom_out).pack(side="left", padx=2)
        self.zoom_label = tk.Label(toolbar, text="100%", bg="#F5F5F5", width=5)
        self.zoom_label.pack(side="left", padx=2)
        tk.Button(toolbar, text="+", width=2, command=self._zoom_in).pack(side="left", padx=2)
        tk.Button(toolbar, text="重置", command=self._reset_zoom).pack(side="left", padx=2)

    def _build_canvas(self):
        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg="#FAFAFA",
            scrollregion=(0, 0, self.CANVAS_LOGICAL_WIDTH, self.CANVAS_LOGICAL_HEIGHT),
        )
        self.hbar = tk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.vbar = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.vbar.grid(row=0, column=1, sticky="ns")

        # 鼠标滚轮：垂直滚动；Shift+滚轮：水平滚动；Ctrl+滚轮：缩放
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """滚轮滚动/缩放。Windows 用 event.delta；Linux 用 event.num 4/5。"""
        # 确定滚动方向：负值表示向上/向左，正值表示向下/向右
        if event.num == 4:
            direction = -1
        elif event.num == 5:
            direction = 1
        else:
            direction = -1 if event.delta > 0 else 1

        # 检测修饰键（event.state 位：Shift=0x1, Ctrl=0x4）
        state = getattr(event, "state", 0)
        if state & 0x4:  # Ctrl：缩放
            if direction < 0:
                self._zoom_in()
            else:
                self._zoom_out()
            return
        if state & 0x1:  # Shift：水平滚动
            self.canvas.xview_scroll(direction, "units")
        else:  # 垂直滚动
            self.canvas.yview_scroll(direction, "units")

    def _zoom_in(self):
        self.scale_factor = round(min(2.0, self.scale_factor + 0.1), 1)
        self._apply_zoom()

    def _zoom_out(self):
        self.scale_factor = round(max(0.3, self.scale_factor - 0.1), 1)
        self._apply_zoom()

    def _reset_zoom(self):
        self.scale_factor = 1.0
        self._apply_zoom()

    def _apply_zoom(self):
        if self.zoom_label:
            self.zoom_label.config(text=f"{int(self.scale_factor * 100)}%")
        w = int(self.CANVAS_LOGICAL_WIDTH * self.scale_factor)
        h = int(self.CANVAS_LOGICAL_HEIGHT * self.scale_factor)
        self.canvas.config(scrollregion=(0, 0, w, h))
        self._render_steps()

    def _render_steps(self):
        self.canvas.delete("all")
        self._node_items.clear()
        x, y = 50, 50
        for step in self.steps:
            item = _NodeItem(
                self.canvas, step, x, y,
                program=self.program,
                on_select=self._on_select,
                on_edit_children=self._on_edit_children,
            )
            self._node_items[step.id] = item
            y += 110
        self._draw_connections()

    def _draw_connections(self):
        self.canvas.delete("connection")
        prev_item = None
        for step in self.steps:
            item = self._node_items.get(step.id)
            if item and prev_item:
                self._draw_line(prev_item, item)
            prev_item = item

    def _draw_line(self, from_item: _NodeItem, to_item: _NodeItem):
        s = self.scale_factor
        x1 = int(from_item.step.x * s) + from_item.width // 2
        y1 = int(from_item.step.y * s) + from_item.height
        x2 = int(to_item.step.x * s) + to_item.width // 2
        y2 = int(to_item.step.y * s)
        seg = max(8, int(15 * s))
        self.canvas.create_line(
            x1, y1, x1, y1 + seg, x2, y2 - seg, x2, y2,
            smooth=True, arrow=tk.LAST, fill="#78909C",
            width=max(1, int(2 * s)),
            tags="connection",
        )

    def _add_node(self, step_type: str):
        import uuid
        step = LogicStep(
            id=str(uuid.uuid4())[:8],
            step_type=step_type,
            x=100,
            y=50 + len(self.steps) * 110,
        )
        self.steps.append(step)
        item = _NodeItem(
            self.canvas, step, step.x, step.y,
            program=self.program,
            on_select=self._on_select,
            on_edit_children=self._on_edit_children,
        )
        self._node_items[step.id] = item
        self._draw_connections()
        if self.on_change:
            self.on_change()

    def _on_select(self, item: _NodeItem):
        if self._selected:
            self._selected.set_color(NODE_COLORS.get(self._selected.step.step_type, "#FFFFFF"))
        self._selected = item
        item.set_color("#FFEB3B")

    def _on_edit_children(self, step: LogicStep):
        ContainerEditor(self, step)
        self.wait_window(self.children[-1])
        if self._selected:
            self._selected.refresh_text()
        self._draw_connections()
        if self.on_change:
            self.on_change()

    def _delete_selected(self):
        if not self._selected:
            return
        step = self._selected.step
        self.steps.remove(step)
        self._render_steps()
        self._selected = None
        if self.on_change:
            self.on_change()

    def get_steps(self) -> List[LogicStep]:
        return self.steps

    def set_steps(self, steps: List[LogicStep]):
        self.steps = steps
        self._render_steps()
