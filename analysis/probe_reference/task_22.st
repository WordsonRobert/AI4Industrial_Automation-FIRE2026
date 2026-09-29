PROGRAM T22
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
    T_Jam : TON;
END_VAR
T_Jam(IN := Entry_Photo_Eye AND NOT Exit_Photo_Eye, PT := T#8s);
IF T_Jam.Q THEN Jam_Alarm := TRUE; END_IF;
IF Stop_Button THEN Jam_Alarm := FALSE; END_IF;
Conveyor_Run := (Start_Button OR Conveyor_Run) AND NOT Stop_Button AND NOT Jam_Alarm;
END_PROGRAM
