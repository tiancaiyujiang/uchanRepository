        IF FI01-HHS-BNG = WK01-BK-HHS-BNG
          THEN
 
 
 
 
 
 
 
 
 
 
 
 
I
F
 
F
I
0
1
-
H
H
S
-
I
D
O
-
Y
M
D
 
>
=
 
W
K
0
1
-
C
D
A
T
E


 
 
 
 
 
 
 
 
 
 
 
 
 
 
T
H
E
N


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


M


O


V


E


 


'


1


'


 


T


O


 


W


K


0


1


-


W


R


T


-


F


L


G


.


 
 
 
 
 
 
 
 
 
 
 
 
 
 
E
L
S
E


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


M


O


V


E


 


S


P


A


C


E


 


T


O


 


W


K


0


1


-


W


R


T


-


F


L


G


.


 
 
 
 
 
 
 
 
 
 
 
 
E
N
D
-
I
F
.
          ELSE
 
 
 
 
 
 
 
 
 
 
 
 
M
O
V
E
 
F
I
0
1
-
H
H
S
-
B
N
G
 
T
O
 
W
K
0
1
-
B
K
-
H
H
S
-
B
N
G
.


 
 
 
 
 
 
 
 
 
 
 
 
I
F
 
F
I
0
1
-
H
H
S
-
S
K
S
S
-
Y
M
D
 
=
 
S
P
A
C
E


 
 
 
 
 
 
 
 
 
 
 
 
 
 
T
H
E
N


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


M


O


V


E


 


'


1


'


 


T


O


 


W


K


0


1


-


W


R


T


-


F


L


G


.


 
 
 
 
 
 
 
 
 
 
 
 
 
 
E
L
S
E


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


I


F


 


F


I


0


1


-


H


H


S


-


I


D


O


-


Y


M


D


 


>


=


 


W


K


0


1


-


C


D


A


T


E






 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


T


H


E


N






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






M






O






V






E






 






'






1






'






 






T






O






 






W






K






0






1






-






W






R






T






-






F






L






G






.






 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


E


L


S


E






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






 






M






O






V






E






 






S






P






A






C






E






 






T






O






 






W






K






0






1






-






W






R






T






-






F






L






G






.






 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


 


E


N


D


-


I


F


.


 
 
 
 
 
 
 
 
 
 
 
 
E
N
D
-
I
F
.
        END-IF.