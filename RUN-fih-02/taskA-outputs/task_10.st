PROGRAM Auto_CycleControl
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
TON_Wash(IN := Car_Present AND Start_Button, PT := T#20s);
TON_Rinse(IN := Car_Present AND Start_Button, PT := T#15s);
TON_Dry(IN := Car_Present AND Start_Button, PT := T#10s);
Wash_Pump := TON_Wash.Q;
Rinse_Valve := TON_Rinse.Q;
Dryer_Fan := TON_Dry.Q;
Cycle_Complete := TON_Dry.Q;
END_PROGRAM