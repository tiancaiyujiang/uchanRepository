# COBOL 代码生成器 - KWBAC1 迭代版

基于真实详细设计书（KWBAC1：介護保険資格情報抽出処理）迭代的 COBOL 代码生成工具。

## 功能特性

### 输入输出文件
- 支持多个输入/输出文件（最多各 10 个）
- COPYBOOK 读取为可选项
- 无 COPYBOOK 时可手动维护字段定义
- 实时预览生成的 DATA DIVISION 代码

### 自定义变量
- 阶数：01 / 03 / 05 / 77 / 88 等
- 变量名、数据类型下拉选择、长度、初始值
- 追加后显示在列表中
- 自动生成到 WORKING-STORAGE 或 LINKAGE SECTION

### 字段映射
- 输入字段 → 输出字段可视化映射
- 同名自动映射

### 逻辑编辑器
- 拖拽画布节点编辑器
- 支持 IF / EVALUATE / COMPUTE / PERFORM / MOVE / INITIALIZE / CALL
- IF / PERFORM 容器节点可进入子步骤编辑

### 代码生成
- KWBAC1 风格框架：MAIN-PROC / JUNBI / BUNPAI / EDIT / WRITE / SYURYO
- COPYBOOK 内联（本地测试）或 COPY PREFIXING（真实环境）
- 单文件 exe 打包

## 快速开始

双击运行：

```text
CobolGenerater/dist/CobolGenerater.exe
```

### 使用步骤

1. **文件定义**
   - 点击「+ 添加」增加输入/输出文件（最多 10 个）
   - 填写逻辑名、物理名、File Status、前缀
   - 勾选「读取 COPYBOOK」并选择文件，或手动填写字段
   - 点击「保存文件定义并刷新预览」查看 DATA DIVISION

2. **自定义变量**
   - 填写阶数、变量名、数据类型、长度、初始值
   - 点击「追加变量」
   - 变量会显示在列表并生成到 WORKING-STORAGE

3. **字段映射**
   - 点击「同名自动映射」生成 MOVE 规则

4. **逻辑编辑器**
   - 添加节点或点击「生成 BUNPAI 模板」
   - 双击节点编辑属性
   - 容器节点点击「编辑」进入 THEN/ELSE 或循环体

5. **代码预览**
   - 点击「生成 COBOL」
   - 确认后「保存 .cbl」

## 从源码运行

```bash
cd CobolGenerater
source ../venv/bin/activate
python main.py
```

## 重新打包

```bash
cd CobolGenerater
source ../venv/bin/activate
python build.py
```

## 文件结构

```
CobolGenerater/
├── main.py                      # GUI 入口
├── models.py                    # 领域模型
├── copybook_parser.py           # COPYBOOK 解析
├── copybook_inliner.py          # COPYBOOK 内联
├── file_editor.py               # 文件列表 + 自定义变量编辑器
├── logic_editor.py              # 拖拽画布逻辑编辑器
├── logic_generator.py           # 逻辑模型 → COBOL 代码
├── generator.py                 # COBOL 生成器
├── templates/
│   └── kwbac1_framework.cobol.j2
├── build.py                     # PyInstaller 打包脚本
├── dist/CobolGenerater.exe      # 可执行文件
└── README.md
```

## 已知限制

- COPYBOOK 解析暂不支持 REDEFINES / OCCURS
- EVALUATE 的 WHEN 分支图形化编辑较简单
- 主处理逻辑仍默认使用第一个输入文件和第一个输出文件
- 框架子系统调用（KZSA48 / KZSO01 / KZSE02）为简化/占位实现

## 下一步建议

1. 追加 Hitachi 框架子系统调用
2. 完善 EVALUATE 图形化编辑
3. 用真实 `人間作成_KWBAC1.CBL` 做 diff 逼近
4. UI 体验优化（字段下拉选择、节点对齐等）
