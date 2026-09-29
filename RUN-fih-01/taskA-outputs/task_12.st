PROGRAM WeightCheckControl
VAR_INPUT
    Weight_Input : INT;
    Target_Weight : INT;
    Photo_Eye : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Pusher : BOOL;
END_VAR
VAR
    Scaled_Weight : REAL;
END_VAR
Scaled_Weight := Weight_Input / 10.0;
IF NOT Photo_Eye THEN
    Reject_Pusher := FALSE;
ELSIF Scaled_Weight - Target_Weight / 10.0 < 5.0 OR Target_Weight / 10.0 + 5.0 > Scaled_Weight THEN
    Reject_Pusher := TRUE;
END_IF;
END_PROGRAM