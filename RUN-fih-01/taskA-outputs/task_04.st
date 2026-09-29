PROGRAM FillingCycleControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Bottle_Present : BOOL;
    Level_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Fill_Valve : BOOL;
END_VAR
IF Stop_Button THEN
    Fill_Valve := FALSE;
    Bottle_Count := 0;
ELSIF Start_Button AND NOT Fill_Valve THEN
    Fill_Valve := Bottle_Present AND NOT Level_Sensor;
END_IF;
IF Fill_Valve THEN
    Bottle_Count := Bottle_Count + 1;
END_IF;
END_PROGRAM