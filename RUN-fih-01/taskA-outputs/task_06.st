PROGRAM SafetyControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    E_Stop : BOOL;
    Reset_Button : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
    EStop_Lamp : BOOL;
END_VAR
Motor_Run := (Start_Button AND NOT Stop_Button OR NOT E_Stop) AND Reset_Button;
EStop_Lamp := E_Stop;
END_PROGRAM