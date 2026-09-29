PROGRAM TempControl
VAR_INPUT
    Temp_Sensor : INT;
END_VAR
VAR_OUTPUT
    Fan1 : BOOL;
    Fan2 : BOOL;
END_VAR
Temp_Sensor := REAL_TO_INT(Temp_Sensor / 10.0);
Fan1 := Temp_Sensor >= 300;
Fan2 := Temp_Sensor >= 350;
END_PROGRAM