PROGRAM weight_check
VAR_INPUT
    Weight_Input : INT;
    Target_Weight : INT;
    Photo_Eye : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Pusher : BOOL;
END_VAR
VAR
    TON0 : TON;
END_VAR
TON0(IN := ABS(Weight_Input - Target_Weight) <= 500, PT := T#500MS);
Reject_Pusher := Photo_Eye AND NOT TON0.Q;
END_PROGRAM