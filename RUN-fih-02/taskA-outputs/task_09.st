PROGRAM program0
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
Door_Motor_Open := NOT Obstacle_Sensor AND Open_Button;
Door_Motor_Close := Close_Button AND NOT Open_Limit;
END_PROGRAM