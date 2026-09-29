PROGRAM door_control
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
VAR
    State : INT;
    R_TRIG0 : R_TRIG;
    _TMP_AND5_OUT : BOOL;
END_VAR
R_TRIG0(CLK := Open_Button);
IF R_TRIG0.Q THEN
    State := 1;
ELSIF Close_Button THEN
    State := 2;
END_IF;
CASE State OF
    1:
        IF Open_Limit THEN
            State := 0;
        END_IF;
        Door_Motor_Open := TRUE;
        Door_Motor_Close := FALSE;
    2:
        IF Closed_Limit THEN
            State := 0;
        END_IF;
        Door_Motor_Close := TRUE;
        Door_Motor_Open := FALSE;
    0:
        Door_Motor_Open := FALSE;
        Door_Motor_Close := FALSE;
END_CASE;
IF Obstacle_Sensor THEN
    State := 1;
END_IF;
END_PROGRAM