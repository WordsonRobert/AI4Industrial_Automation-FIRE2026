PROGRAM T30
VAR_INPUT
    RPM_Set : INT;
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Vision_Sensor : INT;
END_VAR
VAR_OUTPUT
    Conveyor_Run : INT;
    start_light : BOOL;
    Digital_Display : INT;
    display_box_counter : INT;
    blue_box_counter : INT;
    grey_box_counter : INT;
    green_box_counter : INT;
END_VAR
start_light := (Start_Button OR start_light) AND NOT Stop_Button;
IF start_light THEN Conveyor_Run := RPM_Set; ELSE Conveyor_Run := 0; END_IF;
Digital_Display := RPM_Set;
END_PROGRAM
