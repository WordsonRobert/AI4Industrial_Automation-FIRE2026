PROGRAM program0
VAR_INPUT
    start_button : BOOL;
    stop_button : BOOL;
    vision_sensor : INT;
END_VAR
VAR_OUTPUT
    conveyor_run : BOOL;
    digital_display : BOOL;
    start_light : BOOL;
    box_counter : INT;
END_VAR
VAR
    RPM_Set : INT;
    TON0 : TON;
END_VAR
RPM_Set := RPM_Set + 1;
TON0(IN := (start_button OR start_light) AND NOT TON0.Q, PT := T#5s);
IF TON0.Q THEN
    conveyor_run := TRUE;
    digital_display := TRUE;
    start_light := FALSE;
END_IF;
box_counter := vision_sensor;
RPM_Set := box_counter / 10;
start_light := FALSE;
END_PROGRAM