PROGRAM ConveyorControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Speed_Select : BOOL;
    Low_Speed_Set : INT;
    High_Speed_Set : INT;
END_VAR
VAR_OUTPUT
    Conveyor_Speed : INT;
    Running_Lamp : BOOL;
END_VAR
IF Stop_Button THEN
    Conveyor_Speed := 0;
    Running_Lamp := FALSE;
ELSIF Start_Button THEN
    Conveyor_Speed := Low_Speed_Set + High_Speed_Set;
    Running_Lamp := TRUE;
END_IF;
END_PROGRAM