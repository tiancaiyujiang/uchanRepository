      *> 本程序由 COBOL Generator 自动生成
      *> 程序ID: KWBAC1
       IDENTIFICATION DIVISION.
       PROGRAM-ID. KWBAC1.
       AUTHOR. COBOL Generator.
       DATE-WRITTEN. 2026/07/04.
       REMARKS. 自動生成.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. HITAC.
       OBJECT-COMPUTER. HITAC.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT KWFAC0
              ASSIGN TO SYS010-DA-DK-S
              FILE STATUS IS W-FS-KWFAC0
              ACCESS MODE IS SEQUENTIAL.
           SELECT KWFAC1
              ASSIGN TO SYS020-DA-DK-S
              FILE STATUS IS W-FS-KWFAC1
              ACCESS MODE IS SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  KWFAC0
           LABEL RECORD STANDARD
           BLOCK CONTAINS 0 CHARACTERS
           RECORDING MODE F.
           COPY KA101A0C PREFIXING FI01-.
       FD  KWFAC1
           LABEL RECORD STANDARD
           BLOCK CONTAINS 0 CHARACTERS
           RECORDING MODE F.
           COPY KWDFAC1 PREFIXING FO01-.

       WORKING-STORAGE SECTION.
      *> 文件计数器与 EOF 标志
       01  KWFAC0-WORK-AREA.
           03  KWFAC0-CNT        PIC 9(07).
           03  KWFAC0-END-SW     PIC X(03).
       01  KWFAC1-WORK-AREA.
           03  KWFAC1-CNT        PIC 9(07).
      *> 处理日与5年前日期
       01  WK01-SDATE.
           03  WK01-SYYYY        PIC 9(04).
           03  WK01-SMM          PIC X(02).
           03  WK01-SDD          PIC X(02).
       01  WK01-CDATE.
           03  WK01-CYYYY        PIC 9(04).
           03  WK01-CMM          PIC X(02).
           03  WK01-CDD          PIC X(02).
      *> 判定用工作区
       01  WK01-AREA.
           03  WK01-BK-HHS-BNG   PIC X(10).
           03  WK01-WRT-FLG      PIC X(01).
       01  W-KWFAC0-AREA.
           03  W-FS-KWFAC0       PIC X(02).
       01  W-KWFAC1-AREA.
           03  W-FS-KWFAC1       PIC X(02).
      *> 常量区
       01  CONSTANT-AREA.
           03  CON-KWFAC0-AL     PIC X(06) VALUE 'KWFAC0'.
           03  CON-KWFAC1-AL     PIC X(06) VALUE 'KWFAC1'.
           03  CON-KWBAC1-AL     PIC X(06) VALUE 'KWBAC1'.
           03  CON-END-AL        PIC X(03) VALUE 'END'.
           03  CON-1-AL          PIC X(01) VALUE '1'.
           03  CON-OK-AL         PIC X(02) VALUE '00'.

       LINKAGE SECTION.
       PROCEDURE DIVISION.
      ******************************************************************
      *    メインプロセス                                              *
      ******************************************************************
       MAIN-PROC SECTION.
       MAIN-PROC-010.
           PERFORM JUNBI-PROC.
           PERFORM FILE-OPEN-PROC.
           PERFORM KWFAC0-READ-PROC.
           PERFORM WITH TEST BEFORE
             UNTIL KWFAC0-END-SW = CON-END-AL
               PERFORM BUNPAI-PROC
               IF WK01-WRT-FLG = CON-1-AL
                 THEN
                   PERFORM KWFAC1-EDIT-PROC
                   PERFORM KWFAC1-WRITE-PROC
                 ELSE
                   CONTINUE
               END-IF
               PERFORM KWFAC0-READ-PROC
           END-PERFORM.
           PERFORM FILE-CLOSE-PROC.
           PERFORM SYURYO-PROC.
       MAIN-PROC-999.
           STOP RUN.

      ******************************************************************
      *    KWFAC1-EDIT 編集処理                                        *
      ******************************************************************
       KWFAC1-EDIT-PROC SECTION.
       KWFAC1-EDIT-PROC-010.
      *> 初始化输出记录
           INITIALIZE FO01-KWDFAC1-REC.
      *> 字段映射 MOVE
       KWFAC1-EDIT-PROC-999.
           EXIT.

      ******************************************************************
      *    BUNPAI 分配・判定処理                                       *
      ******************************************************************
       BUNPAI-PROC SECTION.
       BUNPAI-PROC-010.
           MOVE SPACE TO WK01-WRT-FLG.
            IF FI01-HHS-IDO-YMD >= WK01-CDATE
              THEN
                MOVE '1' TO WK01-WRT-FLG.
              ELSE
                MOVE SPACE TO WK01-WRT-FLG.
            END-IF.
       BUNPAI-PROC-999.
           EXIT.

      ******************************************************************
      *    JUNBI 準備処理                                              *
      ******************************************************************
       JUNBI-PROC SECTION.
       JUNBI-PROC-010.
      *> 初始化
           INITIALIZE KWFAC0-WORK-AREA
           INITIALIZE KWFAC1-WORK-AREA
           INITIALIZE WK01-SDATE
           INITIALIZE WK01-CDATE
           INITIALIZE WK01-AREA
           INITIALIZE W-KWFAC0-AREA
           INITIALIZE W-KWFAC1-AREA.
      *> 获取系统日期（简化版，真实环境应 CALL KZSA48）
           MOVE FUNCTION CURRENT-DATE(1:8) TO WK01-SDATE.
           MOVE WK01-SDATE TO WK01-CDATE.
           COMPUTE WK01-CYYYY = WK01-CYYYY - 5.
       JUNBI-PROC-999.
           EXIT.

      ******************************************************************
      *    ファイルオープン                                            *
      ******************************************************************
       FILE-OPEN-PROC SECTION.
       FILE-OPEN-PROC-010.
           OPEN INPUT KWFAC0.
           OPEN OUTPUT KWFAC1.
       FILE-OPEN-PROC-999.
           EXIT.

      ******************************************************************
      *    ファイルクローズ                                            *
      ******************************************************************
       FILE-CLOSE-PROC SECTION.
       FILE-CLOSE-PROC-010.
           CLOSE KWFAC0.
           CLOSE KWFAC1.
       FILE-CLOSE-PROC-999.
           EXIT.

      ******************************************************************
      *    KWFAC0 読み込み                                             *
      ******************************************************************
       KWFAC0-READ-PROC SECTION.
       KWFAC0-READ-PROC-010.
           READ KWFAC0
             AT END MOVE CON-END-AL TO KWFAC0-END-SW.
           IF KWFAC0-END-SW NOT = CON-END-AL
             THEN
               ADD 1 TO KWFAC0-CNT
           END-IF.
       KWFAC0-READ-PROC-999.
           EXIT.

      ******************************************************************
      *    KWFAC1 書き出し                                             *
      ******************************************************************
       KWFAC1-WRITE-PROC SECTION.
       KWFAC1-WRITE-PROC-010.
           WRITE FO01-KWDFAC1-REC.
           ADD 1 TO KWFAC1-CNT.
       KWFAC1-WRITE-PROC-999.
           EXIT.

      ******************************************************************
      *    SYURYO 終了処理                                             *
      ******************************************************************
       SYURYO-PROC SECTION.
       SYURYO-PROC-010.
           DISPLAY 'KWFAC0 REC CNT = ' KWFAC0-CNT.
           DISPLAY 'KWFAC1 REC CNT = ' KWFAC1-CNT.
       SYURYO-PROC-999.
           EXIT.