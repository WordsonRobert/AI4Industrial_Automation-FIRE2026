PROGRAM T18
VAR_INPUT
    Part_Detect : BOOL;
    Part_Good : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Cylinder : BOOL;
END_VAR
VAR
    Trig : R_TRIG;
    Pulse : TP;
END_VAR
Trig(CLK := Part_Detect);
Pulse(IN := Trig.Q AND NOT Part_Good, PT := T#500ms);
Reject_Cylinder := Pulse.Q;
END_PROGRAM
