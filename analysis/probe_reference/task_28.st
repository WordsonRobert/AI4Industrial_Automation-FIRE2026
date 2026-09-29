PROGRAM T28
VAR_INPUT
    RPM_Set : INT;
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Digital_Display : INT;
    Conveyor_Run : INT;
END_VAR
VAR
    Running : BOOL;
END_VAR
Running := (Start_Button OR Running) AND NOT Stop_Button;
IF Running THEN Conveyor_Run := RPM_Set; ELSE Conveyor_Run := 0; END_IF;
Digital_Display := RPM_Set;
END_PROGRAM
