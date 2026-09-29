PROGRAM SafetyCurtainControl
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Light_Curtain_Clear : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor_Run : BOOL;
    Safety_Fault_Lamp : BOOL;
END_VAR
Conveyor_Run := (Start_Button OR IdStop_Button) AND Light_Curtain_Clear;
Safety_Fault_Lamp := NOT Light_Curtain_Clear;
END_PROGRAM