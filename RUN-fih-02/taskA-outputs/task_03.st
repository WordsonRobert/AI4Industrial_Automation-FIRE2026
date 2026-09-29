PROGRAM program0
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Overload_Trip : BOOL;
    Reset_Button : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
    Fault_Lamp : BOOL;
END_VAR
VAR
    TON0 : TON;
END_VAR
TON0(IN := NOT Fault_Lamp AND (Start_Button OR Stop_Button), PT := T#5s);
Motor_Run := TON0.Q;
Fault_Lamp := Overload_Trip AND NOT TON0.Q;
END_PROGRAM