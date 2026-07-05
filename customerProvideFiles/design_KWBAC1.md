# design.md

## 1. プログラム基本情報

* 
**Program ID**: `KWBAC1` 


* 
**Program Name**: 介護保険資格情報抽出処理(セットアップ) 


* **Overview**:
* 被保険者履歴アンロードファイルを入力とし、異動年月日が処理日より5年前以降のデータを抽出する。
* また、異動年月日が5年前より前であっても、現在資格を有している（資格喪失していない）被保険者データも抽出対象とする。





## 2. 入出力定義

### 2.1 入力ファイル (Input)

* 
**Input Type**: **File** (※Case B: 入力が「File」の場合 を適用) 


* **Logical Name**: `KWFACO`
* **Physical Name (ASSIGN)**: `SYS010`
* **Copybook**: `KA101A0C`
* **File Status Variable**: `W-FS-KWFACO`
* **Record Prefix**: `F101-`

### 2.2 出力ファイル (Output)

* 
**Output Type**: **File** 


* **Logical Name**: `KWFAC1`
* **Physical Name (ASSIGN)**: `SYS020`
* **Copybook**: `KWDFACT`
* **File Status Variable**: `W-FS-KWFAC1`
* **Record Prefix**: `F001-`

## 3. 処理ロジック要件

### 3.1 準備処理 (JUNBI-PROC)

* **日付取得**: 共通モジュール `KZSA48` をコールし、処理日付を取得する。
* 
**5年前算出**: 取得した処理日付から「5年前」の日付を算出する（例: 処理日が20260219なら、20210219）。



### 3.2 抽出・分配条件 (Selection Criteria)

入力レコードに対し、以下のいずれかの条件を満たす場合にデータを出力する。

1. **直近異動者**:
* `F101-HHS-SKST-YMD` (資格取得年月日/異動日) ≧ `5年前の日付`


2. **有効資格保持者** (5年以上異動がないが資格がある):
* `F101-HHS-SKST-YMD` < `5年前の日付`  **AND**
* `F101-HHS-SKSS-YMD` (資格喪失年月日) = `SPACE` (または Low-Value / 空白)



### 3.3 編集・移送要件 (Mapping)
KWBAC1_edit.csvの仕様で編集する。(PREFIXING込みで編集仕様が記載されている。)