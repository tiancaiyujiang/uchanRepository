      *> 本程序由 COBOL Generator 自动生成
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPGM.
       AUTHOR. COBOL Generator.
       REMARKS. MVP test.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUTTEST01_IN ASSIGN TO "../dataSet/inputTest01.csv"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT INPUTTEST01_IN_OUT ASSIGN TO "INPUTTEST01_IN-OUT.txt"
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUTTEST01_IN.
       01  INPUTTEST01_IN-RECORD.
           05  CUSTOMER_ID PIC X(20).
           05  CUSTOMER_NAME PIC X(20).
           05  AGE PIC 9(5).
           05  CITY PIC X(20).
           05  PRODUCT_CODE PIC X(20).
           05  PRODUCT_NAME PIC X(20).
           05  QUANTITY PIC 9(5).
           05  PRICE PIC 9(5).
           05  ORDER_STATUS PIC X(20).
           05  REMARK PIC X(20).

       FD  INPUTTEST01_IN_OUT.
       01  INPUTTEST01_IN_OUT-RECORD.
           05  CUSTOMER_ID PIC X(20).
           05  CUSTOMER_NAME PIC X(20).
           05  AGE PIC 9(5).
           05  CITY PIC X(20).
           05  PRODUCT_CODE PIC X(20).
           05  PRODUCT_NAME PIC X(20).
           05  QUANTITY PIC 9(5).
           05  PRICE PIC 9(5).
           05  ORDER_STATUS PIC X(20).
           05  REMARK PIC X(20).

       WORKING-STORAGE SECTION.
       01  WS-EOF-SWITCH     PIC X VALUE 'N'.
       01  WS-RECORD-COUNT   PIC 9(10) VALUE 0.
       01  WS-DISPLAY-MSG    PIC X(80).

       PROCEDURE DIVISION.
       MAIN-LOGIC.
           OPEN INPUT INPUTTEST01_IN
           OPEN OUTPUT INPUTTEST01_IN_OUT

           PERFORM UNTIL WS-EOF-SWITCH = 'Y'
               READ INPUTTEST01_IN
                   AT END
                       MOVE 'Y' TO WS-EOF-SWITCH
                   NOT AT END
                       ADD 1 TO WS-RECORD-COUNT
                       MOVE INPUTTEST01_IN-RECORD
                            TO INPUTTEST01_IN_OUT-RECORD
                       WRITE INPUTTEST01_IN_OUT-RECORD
               END-READ
           END-PERFORM

           CLOSE INPUTTEST01_IN
           CLOSE INPUTTEST01_IN_OUT

           STRING "总处理记录数: " DELIMITED BY SIZE
                  WS-RECORD-COUNT DELIMITED BY SIZE
                  INTO WS-DISPLAY-MSG
           DISPLAY WS-DISPLAY-MSG

           STOP RUN.
