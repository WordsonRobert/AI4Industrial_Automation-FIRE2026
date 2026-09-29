PROGRAM DosingControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Flow_A_Pulse : BOOL;
END_VAR
VAR_OUTPUT
    Valve_A : BOOL;
    Valve_B : BOOL;
END_VAR
VAR
    CTU0 : CTU;
    R_TRIG0 : R_TRIG;
    TP0 : TP;
END_VAR
R_TRIG0(CLK := Flow_A_Pulse);
CTU0(CU := R_TRIG0.Q, R := Stop_Button, PV := 50);
TP0(IN := Start_Button AND NOT Stop_Button, PT := T#1s);
Valve_A := TP0.Q;
Valve_B := TP0.Q AND MOD(CTU0.CV, 4) = 0;
END_PROGRAM