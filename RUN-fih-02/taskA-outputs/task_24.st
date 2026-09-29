PROGRAM LightChaseControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Lamp1 : BOOL;
    Lamp2 : BOOL;
    Lamp3 : BOOL;
    Lamp4 : BOOL;
END_VAR
VAR
    CTU0 : CTU;
    R_TRIG0 : R_TRIG;
    TP0 : TP;
END_VAR
R_TRIG0(CLK := Start_Button);
CTU0(CU := R_TRIG0.Q, R := Stop_Button, PV := 4);
IF CTU0.Q THEN
    TP0(IN := TRUE, PT := T#500ms);
    Lamp1 := TP0.Q;
    Lamp2 := Lamp1;
    Lamp3 := Lamp2;
    Lamp4 := Lamp3;
END_IF;
Lamp1 := NOT Lamp1;
Lamp2 := NOT Lamp2;
Lamp3 := NOT Lamp3;
Lamp4 := NOT Lamp4;
END_PROGRAM