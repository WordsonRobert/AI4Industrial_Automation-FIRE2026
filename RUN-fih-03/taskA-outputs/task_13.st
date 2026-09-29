PROGRAM program0
VAR_INPUT
    Temp_Sensor : INT;
    Setpoint : INT;
END_VAR
VAR_OUTPUT
    Heater : BOOL;
END_VAR
VAR
    last_temp : INT;
END_VAR
Heater := last_temp - Temp_Sensor <= 5 AND Setpoint - Temp_Sensor >= 5;
last_temp := Temp_Sensor;
END_PROGRAM