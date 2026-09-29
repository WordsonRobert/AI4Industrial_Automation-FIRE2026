PROGRAM ElevatorControl
VAR_INPUT
    call_floor1 : BOOL;
    call_floor2 : BOOL;
    at_floor1 : BOOL;
    at_floor2 : BOOL;
END_VAR
VAR_OUTPUT
    motor_up : BOOL;
    motor_down : BOOL;
END_VAR
VAR
    floor_sensor1 : BOOL;
    floor_sensor2 : BOOL;
    current_floor : INT;
    last_motor_up : BOOL;
    last_motor_down : BOOL;
END_VAR
floor_sensor1 := at_floor1;
floor_sensor2 := at_floor2;
IF call_floor1 AND NOT at_floor1 THEN
    current_floor := 1;
    motor_up := TRUE;
    motor_down := FALSE;
    last_motor_up := TRUE;
    last_motor_down := FALSE;
ELSIF call_floor2 AND NOT at_floor2 THEN
    current_floor := 2;
    motor_up := FALSE;
    motor_down := TRUE;
    last_motor_up := FALSE;
    last_motor_down := TRUE;
END_IF;
IF current_floor = 1 THEN
    motor_up := FALSE;
    motor_down := TRUE;
ELSIF current_floor = 2 THEN
    motor_up := FALSE;
    motor_down := FALSE;
END_IF;
IF last_motor_up AND NOT motor_up THEN
    motor_up := TRUE;
ELSIF last_motor_down AND NOT motor_down THEN
    motor_down := TRUE;
END_IF;
END_PROGRAM