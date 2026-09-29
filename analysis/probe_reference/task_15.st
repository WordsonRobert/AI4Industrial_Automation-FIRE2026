PROGRAM T15
VAR_INPUT
    Pressure_Sensor : INT;
END_VAR
VAR_OUTPUT
    Compressor_Motor : BOOL;
END_VAR
IF Pressure_Sensor < 80 THEN Compressor_Motor := TRUE;
ELSIF Pressure_Sensor > 120 THEN Compressor_Motor := FALSE; END_IF;
END_PROGRAM
