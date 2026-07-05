"""领域模型：COBOL 生成器核心数据结构。"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Field:
    """CSV 推断阶段的临时字段。"""
    name: str
    pic: str
    length: int = 0
    field_type: str = "string"
    comment: str = ""


@dataclass
class FileConfig:
    """CSV 文件配置（MVP 遗留）。"""
    name: str
    file_path: str
    record_length: int = 0
    fields: List[Field] = field(default_factory=list)
    is_csv: bool = False


@dataclass
class CopybookField:
    """COPYBOOK 中的一个字段定义。"""
    name: str                       # 字段名，如 HHS-BNG
    full_name: str                  # 含前缀的完整名，如 FI01-HHS-BNG
    pic: str                        # PIC 定义，如 X(10)
    level: int                      # COBOL 层级，如 5
    parent: Optional[str] = None    # 父级字段名
    start_pos: int = 1              # 在记录中的起始位置
    length: int = 0                 # 字段长度
    comment: str = ""               # 注释
    redefines: Optional[str] = None # REDEFINES 目标
    occurs: int = 0                 # OCCURS 次数，0 表示无


@dataclass
class FileDefinition:
    """文件定义（输入或输出）。"""
    name: str                       # 逻辑名，如 KWFAC0
    physical_name: str              # ASSIGN TO，如 SYS010-DA-DK-S
    file_status: str                # FILE STATUS 变量，如 W-FS-KWFAC0
    copybook_name: str              # COPY 句名，如 KA101A0C
    prefix: str                     # PREFIXING，如 FI01-
    record_name: str = ""           # 01 级记录名，如 FI01-DB-REC
    fields: List[CopybookField] = field(default_factory=list)
    is_input: bool = True

    def __post_init__(self):
        for c in "-. ":
            self.prefix = self.prefix.replace(c, "_")
        self.prefix = self.prefix.strip("_").upper()


@dataclass
class Operand:
    """操作数：字段、变量、字面量或表达式。"""
    op_type: str                    # FIELD / VARIABLE / LITERAL / EXPRESSION
    value: str
    pic: str = ""                   # 仅 FIELD 类型使用
    literal_type: str = "TEXT"      # 仅 LITERAL 类型使用：NUMERIC / TEXT


@dataclass
class Condition:
    """IF / EVALUATE / PERFORM UNTIL 等使用的条件。"""
    left: Operand
    operator: str                   # = / NOT = / < / > / <= / >= / AND / OR
    right: Operand
    logical_op: str = ""            # 与下一个 Condition 的组合关系（AND / OR / 空）


@dataclass
class EvaluateCase:
    """EVALUATE 的 WHEN 分支。"""
    conditions: List[Condition]     # 空列表表示 WHEN OTHER
    label: str = ""
    body: List['LogicStep'] = field(default_factory=list)


@dataclass
class MappingRule:
    """字段映射规则：用于生成 MOVE 语句。"""
    source: Operand
    target: Operand
    condition: Optional[Condition] = None


@dataclass
class LogicStep:
    """逻辑编辑器中的一个节点/步骤。"""
    id: str
    step_type: str                  # IF / EVALUATE / COMPUTE / PERFORM / MOVE /
                                    # INITIALIZE / CONTINUE / CALL / SECTION / PARAGRAPH
    label: str = ""                 # 显示名称/段落名
    x: int = 100
    y: int = 100
    width: int = 180
    height: int = 80

    # IF 专用
    conditions: List[Condition] = field(default_factory=list)
    then_body: List['LogicStep'] = field(default_factory=list)
    else_body: List['LogicStep'] = field(default_factory=list)

    # EVALUATE 专用
    evaluate_subject: Optional[Operand] = None
    evaluate_cases: List[EvaluateCase] = field(default_factory=list)

    # COMPUTE 专用
    compute_target: Optional[Operand] = None
    # 表达式由运算单元与运算符交替组成：
    #   运算单元1 + 运算符 + 运算单元2 + 运算符 + 运算单元3 ...
    # 最少需要 2 个运算单元和 1 个运算符。
    compute_operands: List[Operand] = field(default_factory=list)
    compute_operators: List[str] = field(default_factory=list)

    # PERFORM 专用
    perform_type: str = ""          # UNTIL / VARYING / TIMES / SECTION
    perform_condition: Optional[Condition] = None
    perform_target: str = ""        # PERFORM 目标段落名
    perform_body: List['LogicStep'] = field(default_factory=list)

    # MOVE 专用：字段映射规则列表
    mapping_rules: List[MappingRule] = field(default_factory=list)

    # CALL 专用
    call_program: str = ""
    call_using: List[Operand] = field(default_factory=list)

    # INITIALIZE 专用
    initialize_targets: List[Operand] = field(default_factory=list)

    # 容器节点：用于可视化分组
    is_container: bool = False
    children: List['LogicStep'] = field(default_factory=list)


@dataclass
class Procedure:
    """COBOL PROCEDURE DIVISION 的一个 SECTION（过程）。"""
    id: str
    name: str                       # SECTION 名，如 CUSTOM-EDIT-PROC
    title: str = ""                 # 界面显示标题
    steps: List[LogicStep] = field(default_factory=list)
    call_point: str = "LOOP"        # LOOP=主读循环内 / MAIN=主流程顺序


@dataclass
class CustomVariable:
    """自定义变量（用于 WORKING-STORAGE 或 DATA DIVISION）。"""
    level: str              # 01 / 03 / 77 / 88 等
    name: str
    var_type: str           # X / 9 / S9 / COMP / COMP-3 等
    length: str             # 长度，如 10 或 10.2
    initial_value: str = ""
    section: str = "WORKING-STORAGE"  # WORKING-STORAGE / LINKAGE / LOCAL-STORAGE

    def __post_init__(self):
        # COBOL 变量名使用连字符分隔
        self.name = self.name.strip().upper().replace("_", "-")
        self.name = "".join(c for c in self.name if c.isalnum() or c == "-")
        # 去除连续连字符并确保不以连字符开头/结尾
        while "--" in self.name:
            self.name = self.name.replace("--", "-")
        self.name = self.name.strip("-")
        if self.name and self.name[0].isdigit():
            self.name = "V-" + self.name

        # 处理界面上带说明的类型，如“X(文本) / 9(数字) / S9(数字)”
        self.var_type = self.var_type.strip().upper()
        if "(" in self.var_type:
            self.var_type = self.var_type.split("(")[0]


@dataclass
class CobolProgram:
    """一个待生成的 COBOL 程序。"""
    program_id: str
    input_files: List[FileDefinition] = field(default_factory=list)
    output_files: List[FileDefinition] = field(default_factory=list)
    custom_variables: List[CustomVariable] = field(default_factory=list)
    working_storage: List[Operand] = field(default_factory=list)
    linkage: List[Operand] = field(default_factory=list)
    procedures: List[Procedure] = field(default_factory=list)
    author: str = "COBOL Generator"
    remarks: str = ""

    # 框架相关
    sysin_param_copybook: str = "KZWO010"
    cmd_param_copybook: str = "KZWO020"
    err_copybook: str = "KZWO040"
    log_output_copybook: str = "KZLSO01"
    abend_copybook: str = "KZLSE02"
    date_module_copybook: str = "KZLSA48"
