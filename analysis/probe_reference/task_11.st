PROGRAM T11
VAR_INPUT
    Box_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Pusher_Cylinder : BOOL;
    Box_Count_Display : INT;
END_VAR
VAR
    Cnt : CTU;
    Push : TP;
END_VAR
Cnt(CU := Box_Sensor, R := Cnt.Q, PV := 5);
Push(IN := Cnt.Q, PT := T#1s);
Cnt(CU := Box_Sensor, R := Cnt.Q, PV := 5);
Pusher_Cylinder := Push.Q;
Box_Count_Display := Cnt.CV;
END_PROGRAM
