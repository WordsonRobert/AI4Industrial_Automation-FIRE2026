PROGRAM Temp_Controller
VAR_INPUT
    Temp_Sensor : INT;
END_VAR
VAR_OUTPUT
    Fan1 : BOOL;
    Fan2 : BOOL;
END_VAR
Fan1 := Temp_Sensor >= 300 AND Temp_Sensor <= 280;
Fan2 := Temp_Sensor >= 350 AND Temp_Sensor <= 330;
END_PROGRAM