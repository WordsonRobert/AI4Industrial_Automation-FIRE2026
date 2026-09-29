PROGRAM MotorPressureControl
VAR_INPUT
    Pressure_Sensor : INT;
END_VAR
VAR_OUTPUT
    Compressor_Motor : BOOL;
END_VAR
Compressor_Motor := Pressure_Sensor <= 80 AND NOT (Pressure_Sensor >= 120);
END_PROGRAM