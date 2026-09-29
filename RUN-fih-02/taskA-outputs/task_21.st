PROGRAM conveyor_control
VAR_INPUT
    Stop_Button : BOOL;
    Light_Curtain_Clear : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
END_VAR
Conveyor_Run := Light_Curtain_Clear AND NOT Stop_Button;
END_PROGRAM