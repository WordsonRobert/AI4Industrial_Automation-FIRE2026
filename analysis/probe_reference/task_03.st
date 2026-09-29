PROGRAM T03
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Overload_Trip : BOOL;
    Reset_Button : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
    Fault_Lamp : BOOL;
END_VAR
IF Overload_Trip THEN
    Fault_Lamp := TRUE;
ELSIF Reset_Button THEN
    Fault_Lamp := FALSE;
END_IF;
Motor_Run := (Start_Button OR Motor_Run) AND NOT Stop_Button AND NOT Fault_Lamp;
END_PROGRAM
