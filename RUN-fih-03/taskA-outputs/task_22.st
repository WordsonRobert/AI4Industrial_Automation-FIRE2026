PROGRAM ConveyorControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Entry_Photo_Eye : BOOL;
    Exit_Photo_Eye : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
    Jam_Alarm : BOOL;
END_VAR
VAR
    TON_Jam_Delay : TON;
END_VAR
TON_Jam_Delay(IN := NOT Exit_Photo_Eye AND Entry_Photo_Eye, PT := T#8s);
Jam_Alarm := TON_Jam_Delay.Q;
IF Stop_Button THEN
    Conveyor_Run := FALSE;
    Jam_Alarm := FALSE;
ELSIF Start_Button THEN
    Conveyor_Run := TRUE;
END_IF;
Conveyor_Run := FALSE;
END_PROGRAM