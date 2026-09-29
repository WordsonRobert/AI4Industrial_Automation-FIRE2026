PROGRAM CONVEYOR_CONTROL
VAR_INPUT
    RPM_Set : INT;
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Vision_Sensor : INT;
END_VAR
VAR_OUTPUT
    Digital_Display : BOOL;
    Conveyor_Run : BOOL;
    start_light : BOOL;
    display_box_counter : INT;
END_VAR
display_box_counter := Vision_Sensor;
start_light := Start_Button;
IF Stop_Button THEN
    Conveyor_Run := FALSE;
ELSIF Start_Button THEN
    Conveyor_Run := TRUE;
END_IF;
Digital_Display := Conveyor_Run;
END_PROGRAM