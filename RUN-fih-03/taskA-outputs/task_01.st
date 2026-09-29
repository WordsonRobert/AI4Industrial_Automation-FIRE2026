PROGRAM TankControl
VAR_INPUT
    Low_Level_Sensor : BOOL;
    High_Level_Sensor : BOOL;
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Fill_Pump : BOOL;
END_VAR
Fill_Pump := (Start_Button OR NOT High_Level_Sensor) AND NOT Stop_Button;
END_PROGRAM