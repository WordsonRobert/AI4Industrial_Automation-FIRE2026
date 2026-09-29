PROGRAM program0
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
    TON_Jam : TON;
END_VAR
TON_Jam(IN := NOT Jam_Alarm AND Entry_Photo_Eye AND (NOT Stop_Button AND Exit_Photo_Eye), PT := T#8s);
Conveyor_Run := NOT TON_Jam.Q;
Jam_Alarm := Jam_Alarm OR TON_Jam.Q;
END_PROGRAM