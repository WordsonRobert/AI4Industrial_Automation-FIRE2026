PROGRAM TankFillControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Low_Level_Sensor : BOOL;
    High_Level_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Fill_Pump : BOOL;
END_VAR
Fill_Pump := Start_Button AND NOT Low_Level_Sensor AND NOT High_Level_Sensor;
END_PROGRAM