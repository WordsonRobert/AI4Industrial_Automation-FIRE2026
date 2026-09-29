PROGRAM T12
VAR_INPUT
    Weight_Input : INT;
    Target_Weight : INT;
    Photo_Eye : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Pusher : BOOL;
END_VAR
VAR
    Trig : R_TRIG;
    Pulse : TP;
END_VAR
Trig(CLK := Photo_Eye);
Pulse(IN := Trig.Q AND ABS(Weight_Input - Target_Weight) > 5, PT := T#500ms);
Reject_Pusher := Pulse.Q;
END_PROGRAM
