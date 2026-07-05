# ZHYCobolGenerator 开发会话笔记

> 本文件用于在不同机器/不同 Kimi Code 会话间恢复上下文。
> 当前会话日期：2026-07-06

---

## 已完成的模块

- [x] MVP 与 exe 打包（PyInstaller）
- [x] 字段映射模块：已从独立页签迁移为逻辑编辑器的 **MOVE 节点**
  - MOVE 节点可编辑多条源 → 目标映射规则
  - 支持同名自动映射
  - 生成连续多条 `MOVE source TO target.`
- [x] 逻辑编辑器
  - 节点拖拽画布、缩放/滚动
  - 节点类型：IF / EVALUATE / COMPUTE / PERFORM / MOVE / INITIALIZE / CALL / SECTION
  - 各节点编辑对话框（多条件 AND/OR、运算单元增删、字段映射列表等）
- [x] COBOL 模板 `kwbac1_framework.cobol.j2`
  - MAIN 顺序执行 INIT / INPUT / EDIT / OUTPUT / STREAM-CLOSE / EXCEPTION
  - 用户 PROC 独立 SECTION + 三段式注释分隔
  - 新增 `STREAM-CLOSE-PROC` 专门关闭输入/输出文件流
- [x] COMPUTE 模块重构：target = 运算单元1 运算符 运算单元2…
- [x] EVALUATE 模块：目标模式 / TRUE 模式、分支增删、每分支多条件 AND/OR
- [x] IF 模块支持多条件 AND/OR
- [x] 自定义变量类型下拉框修正：去重并明确 `X(文本)` / `9(数字)` / `S9(数字)`
- [x] 全流程自测脚本 `CobolGenerater/test_full_flow.py`：CSV → 文件定义 → 自定义变量 → 全部逻辑节点 → COBOL 编译通过

---

## 当前在做的需求

- 暂无明确的下一项开发任务。
- 建议后续方向（可选）：
  - 项目保存/加载功能（把 `CobolProgram` 序列化为 JSON/YAML）
  - PERFORM 循环体图形化编辑完善
  - 支持更多 COBOL 语句（如 STRING、INSPECT、SEARCH）
  - 生成代码的 DATA DIVISION 预览增强

---

## 已知问题和限制

1. **项目保存/加载未实现**：当前程序退出后，所有文件定义、逻辑节点、自定义变量都会丢失，需重新输入。
2. **PERFORM 图形化仍不完善**：PERFORM UNTIL/TIMES/SECTION 的循环体在画布上可视化较简单。
3. **SECTION 节点语义**：当前把 `SECTION` 节点渲染为 PROC 内的一个**段落（paragraph）**，而不是真正的顶层 SECTION，以避免嵌套 SECTION 编译错误。若后续需要真正的独立 SECTION，需重新设计。
4. **CALL 子程序**：生成的 `CALL 'SUB1'` 在编译时不会检查被调程序是否存在，运行时若找不到会失败。
5. **CSV 推断的字段 PIC 比较保守**：字符串默认至少 20 字节，小数统一用隐含小数点 `V`。
6. **自定义变量高级类型**：当前对 `COMP` / `COMP-3` 等类型的 PIC 生成支持不完整，建议需要时直接写完整 PIC（如 `9(5)V99`）。
7. **GnuCOBOL 路径硬编码**：测试脚本默认使用 `D:/ZHYCobolGenerator/GC32M-BDB-x64/bin/cobc`，可通过环境变量 `COBC_PATH` 覆盖。

---

## 打包 / 测试命令

### 环境

- Python 3.10.12
- 虚拟环境：`D:/ZHYCobolGenerator/workspace/venv`
- GnuCOBOL：`D:/ZHYCobolGenerator/GC32M-BDB-x64/bin/cobc`

### 安装依赖

```bash
cd D:/ZHYCobolGenerator/workspace
python -m venv venv
source venv/Scripts/activate   # MINGW/Git Bash
# 或 venv\Scripts\activate.bat  # CMD
pip install -r requirements.txt
```

### 运行 GUI

```bash
source venv/Scripts/activate
cd CobolGenerater
python main.py
```

### 打包 exe

```bash
source venv/Scripts/activate
cd CobolGenerater
pyinstaller CobolGenerater.spec --noconfirm
# 输出：CobolGenerater/dist/CobolGenerater.exe
```

### 运行测试

```bash
source venv/Scripts/activate
cd CobolGenerater

# 单元测试：MOVE 节点
python test_move_mapping.py

# 全流程自测：生成 COBOL 并调用 cobc 编译
# 若 cobc 不在默认路径，先设置：
# export COBC_PATH="/path/to/cobc"
python test_full_flow.py
```

### 手动验证 COBOL 编译

```bash
D:/ZHYCobolGenerator/GC32M-BDB-x64/bin/cobc -free -x -o output.exe source.cbl
```

---

## Git 仓库

- 远程地址：`https://github.com/tiancaiyujiang/uchanRepository.git`
- 已推送内容：源码、模板、测试脚本、`.gitignore`、本笔记
- **未推送到仓库的内容**：`venv/`、`build/`、`dist/`、临时测试输出（已被 `.gitignore` 排除）
- exe 文件随 GitHub Release `v1.0.0` 发布，见仓库 Releases 页面
