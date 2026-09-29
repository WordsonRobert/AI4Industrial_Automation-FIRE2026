PROGRAM program0
VAR_INPUT
    Box_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Pusher_Cylinder : BOOL;
    Box_Count_Display : BOOL;
END_VAR
VAR
    CTU0 : CTU;
    R_TRIG0 : R_TRIG;
    TP0 : TP;
END_VAR
R_TRIG0(CLK := Box_Sensor);
CTU0(CU := R_TRIG0.Q, R := FALSE, PV := 5);
TP0(IN := CTU0.Q, PT := T#1s);
Pusher_Cylinder := TP0.Q;
Box_Count_Display := CTU0.CV;
END_PROGRAM