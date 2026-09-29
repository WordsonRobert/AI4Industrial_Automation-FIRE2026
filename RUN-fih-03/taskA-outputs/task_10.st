PROGRAM AutoCarWashCycle
VAR_INPUT
    Car_Present : BOOL;
    Start_Button : BOOL;
END_VAR
VAR_OUTPUT
    Wash_Pump : BOOL;
    Rinse_Valve : BOOL;
    Dryer_Fan : BOOL;
    Cycle_Complete : BOOL;
END_VAR
VAR
    TON_Wash : TON;
    TON_Rinse : TON;
    TON_Dry : TON;
END_VAR
Wash_Pump := FALSE;
Rinse_Valve := FALSE;
Dryer_Fan := FALSE;
Cycle_Complete := FALSE;
IF Car_Present AND Start_Button THEN
    TON_Wash(IN := TRUE, PT := T#20s);
ELSIF TON_Wash.Q THEN
    TON_Rinse(IN := TRUE, PT := T#15s);
ELSIF TON_Rinse.Q THEN
    TON_Dry(IN := TRUE, PT := T#10s);
ELSIF TON_Dry.Q THEN
    Cycle_Complete := TRUE;
END_IF;
END_PROGRAM