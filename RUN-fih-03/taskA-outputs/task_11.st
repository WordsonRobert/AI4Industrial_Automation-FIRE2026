PROGRAM CyclicCountingAndReset
VAR_INPUT
    box_sensor : BOOL;
END_VAR
VAR_OUTPUT
    pusher_cylinder : BOOL;
    box_count_display : INT;
END_VAR
VAR
    CTU0 : CTU;
    R_TRIG0 : R_TRIG;
    TP0 : TP;
END_VAR
R_TRIG0(CLK := box_sensor);
CTU0(CU := R_TRIG0.Q, R := FALSE, PV := 5);
TP0(IN := CTU0.Q, PT := T#1s);
pusher_cylinder := TP0.Q;
box_count_display := CTU0.CV;
END_PROGRAM