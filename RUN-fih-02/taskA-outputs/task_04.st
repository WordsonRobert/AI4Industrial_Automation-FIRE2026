PROGRAM fill_cycle
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Bottle_Present : BOOL;
    Level_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Fill_Valve : BOOL;
END_VAR
VAR
    Cycle_Start : BOOL;
END_VAR
Cycle_Start := (Bottle_Present OR Level_Sensor) AND NOT Fill_Valve;
IF Cycle_Start THEN
    Fill_Valve := TRUE;
    Bottle_Count := Bottle_Count + 1;
END_IF;
Cycle_Start := FALSE;
END_PROGRAM