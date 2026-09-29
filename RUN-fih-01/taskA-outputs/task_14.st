PROGRAM TempControl
VAR_INPUT
    Temp_Sensor : INT;
END_VAR
VAR_OUTPUT
    Fan1 : BOOL;
    Fan2 : BOOL;
END_VAR
Fan1 := Temp_Sensor >= 300;
Fan2 := Temp_Sensor >= 350;
END_PROGRAM