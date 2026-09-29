PROGRAM T23
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
    Running : BOOL;
    Cnt : CTU;
END_VAR
Running := (Start_Button OR Running) AND NOT Stop_Button;
Valve_A := Running;
Cnt(CU := Flow_A_Pulse AND Running, R := Cnt.Q AND NOT Flow_A_Pulse, PV := 4);
Valve_B := Running AND Cnt.Q;
END_PROGRAM
