PROGRAM program0
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    E_Stop : BOOL;
    Reset_Button : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
END_VAR
Motor_Run := NOT E_Stop AND NOT Stop_Button;
END_PROGRAM