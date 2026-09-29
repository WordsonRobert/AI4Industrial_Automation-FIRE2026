PROGRAM T09
VAR_INPUT
    Open_Button : BOOL;
    Close_Button : BOOL;
    Open_Limit : BOOL;
    Closed_Limit : BOOL;
    Obstacle_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Door_Motor_Open : BOOL;
    Door_Motor_Close : BOOL;
END_VAR
IF Door_Motor_Close AND Obstacle_Sensor THEN
    Door_Motor_Close := FALSE;
    Door_Motor_Open := TRUE;
END_IF;
IF Open_Button AND NOT Door_Motor_Close THEN Door_Motor_Open := TRUE; END_IF;
IF Close_Button AND NOT Door_Motor_Open THEN Door_Motor_Close := TRUE; END_IF;
IF Open_Limit THEN Door_Motor_Open := FALSE; END_IF;
IF Closed_Limit THEN Door_Motor_Close := FALSE; END_IF;
END_PROGRAM
