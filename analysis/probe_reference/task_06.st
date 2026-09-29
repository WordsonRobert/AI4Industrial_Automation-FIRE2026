PROGRAM T06
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
IF E_Stop THEN
    EStop_Lamp := TRUE;
ELSIF Reset_Button THEN
    EStop_Lamp := FALSE;
END_IF;
Motor_Run := (Start_Button OR Motor_Run) AND NOT Stop_Button AND NOT EStop_Lamp;
END_PROGRAM
