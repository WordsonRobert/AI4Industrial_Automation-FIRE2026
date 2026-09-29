PROGRAM T07
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
VAR
    Running : BOOL;
END_VAR
Running := (Start_Button OR Running) AND NOT Stop_Button;
IF NOT Running THEN
    Conveyor_Speed := 0;
ELSIF Speed_Select THEN
    Conveyor_Speed := High_Speed_Set;
ELSE
    Conveyor_Speed := Low_Speed_Set;
END_IF;
Running_Lamp := Running;
END_PROGRAM
