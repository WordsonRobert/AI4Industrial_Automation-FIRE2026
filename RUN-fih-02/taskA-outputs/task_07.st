PROGRAM conveyorControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Speed_Select : BOOL;
END_VAR
VAR_OUTPUT
    Running_Lamp : BOOL;
END_VAR
VAR
    conveyorStopped : BOOL;
    speedMode : BOOL;
END_VAR
conveyorStopped := Start_Button OR Stop_Button;
IF conveyorStopped THEN
    speedMode := FALSE;
    Conveyor_Speed := 0;
    Running_Lamp := FALSE;
ELSIF Speed_Select = TRUE THEN
    speedMode := TRUE;
    Conveyor_Speed := High_Speed_Set;
    Running_Lamp := TRUE;
END_IF;
IF speedMode THEN
    Conveyor_Speed := Low_Speed_Set;
END_IF;
END_PROGRAM