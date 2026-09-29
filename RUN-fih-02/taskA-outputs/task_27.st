PROGRAM program0
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
    Start_Light : BOOL;
END_VAR
VAR
    RPM_Set : INT;
END_VAR
RPM_Set := CONveyor_Run;
Conveyor_Run := Start_Button AND (RPM_Set OR NOT Stop_Button);
Start_Light := Conveyor_Run;
END_PROGRAM