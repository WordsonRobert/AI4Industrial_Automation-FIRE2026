PROGRAM conveyor_control_program
VAR_INPUT
    start_button : BOOL;
    stop_button : BOOL;
    vision_sensor_blue : INT;
    vision_sensor_green : INT;
    vision_sensor_gray : INT;
END_VAR
VAR_OUTPUT
    conveyor_run : BOOL;
    digital_display : BOOL;
    start_light : BOOL;
    display_box_counter : INT;
    blue_box_counter : INT;
    grey_box_counter : INT;
    green_box_counter : INT;
END_VAR
conveyor_run := NOT stop_button AND start_button;
digital_display := conveyor_run;
start_light := start_button OR conveyor_run;
total_boxes := vision_sensor_blue + (vision_sensor_green + vision_sensor_gray);
display_box_counter := total_boxes;
blue_box_counter := vision_sensor_blue;
grey_box_counter := vision_sensor_gray;
green_box_counter := vision_sensor_green;
RPM_Set := total_boxes / 100.0;
END_PROGRAM