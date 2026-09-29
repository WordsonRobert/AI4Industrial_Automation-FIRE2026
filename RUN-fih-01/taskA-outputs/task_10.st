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
Wash_Pump := TON_Wash.Q;
Rinse_Valve := TON_Rinse.Q;
Dryer_Fan := TON_Dry.Q;
Cycle_Complete := TON_Dry.Q;
IF Car_Present AND Start_Button THEN
    TON_Wash(IN := TRUE, PT := T#20s);
ELSIF TON_Wash.Q THEN
    TON_Rinse(IN := TRUE, PT := T#15s);
ELSIF TON_Rinse.Q THEN
    TON_Dry(IN := TRUE, PT := T#10s);
END_IF;
END_PROGRAM