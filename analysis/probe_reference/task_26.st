PROGRAM T26
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
END_VAR
Conveyor_Run := (Start_Button OR Conveyor_Run) AND NOT Stop_Button;
END_PROGRAM
