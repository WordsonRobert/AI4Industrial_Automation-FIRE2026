PROGRAM ElevatorControl
VAR_INPUT
    Call_Floor1 : BOOL;
    Call_Floor2 : BOOL;
    At_Floor1 : BOOL;
    At_Floor2 : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Up : BOOL;
    Motor_Down : BOOL;
END_VAR
Motor_Up := (Call_Floor2 OR Call_Floor1) AND NOT At_Floor2;
Motor_Down := (Call_Floor2 OR Call_Floor1) AND NOT At_Floor1;
END_PROGRAM