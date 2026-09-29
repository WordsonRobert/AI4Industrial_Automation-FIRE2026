PROGRAM conveyor_rpm_set
VAR_INPUT
    RPM_Set : INT;
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
    start_light : BOOL;
END_VAR
Conveyor_Run := Start_Button AND NOT Stop_Button;
start_light := Conveyor_Run;
END_PROGRAM