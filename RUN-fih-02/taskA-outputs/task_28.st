PROGRAM program0
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    RPM_Set : INT;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
    Digital_Display : INT;
END_VAR
VAR
    TON_Conveyor : TON;
END_VAR
TON_Conveyor(IN := Start_Button AND NOT TON_Conveyor.Q, PT := T#2s);
RPM_RPM := RPM_Set;
Digital_Display := RPM_RPM;
Conveyor_Run := TON_Conveyor.Q;
END_PROGRAM