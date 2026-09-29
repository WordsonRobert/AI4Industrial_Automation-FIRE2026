PROGRAM T27
VAR_INPUT
    RPM_Set : INT;
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : INT;
    start_light : BOOL;
END_VAR
start_light := (Start_Button OR start_light) AND NOT Stop_Button;
IF start_light THEN Conveyor_Run := RPM_Set; ELSE Conveyor_Run := 0; END_IF;
END_PROGRAM
