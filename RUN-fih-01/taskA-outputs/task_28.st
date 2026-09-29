PROGRAM CONVEYOR_RPM_CONTROL
VAR_INPUT
    rpm_set : INT;
    start_button : BOOL;
    stop_button : BOOL;
END_VAR
VAR_OUTPUT
    digital_display : INT;
    conveyor_run : BOOL;
END_VAR
digital_display := rpm_set;
IF stop_button THEN
    conveyor_run := FALSE;
ELSIF start_button THEN
    conveyor_run := TRUE;
END_IF;
END_PROGRAM