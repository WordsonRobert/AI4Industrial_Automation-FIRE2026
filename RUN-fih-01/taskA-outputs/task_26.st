PROGRAM program0
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
END_VAR
Conveyor_Run := Start_Button AND NOT Stop_Button;
END_PROGRAM