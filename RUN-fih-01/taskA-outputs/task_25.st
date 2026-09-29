PROGRAM PHControl
VAR_INPUT
    pH_Sensor : INT;
END_VAR
VAR_OUTPUT
    Acid_Pump : BOOL;
    Base_Pump : BOOL;
END_VAR
VAR
    Scaled_PHSensor : REAL;
END_VAR
Scaled_PHSensor := pH_Sensor * 0.01;
IF Scaled_PHSensor > 720.0 THEN
    Acid_Pump := TRUE;
ELSIF Scaled_PHSensor < 680.0 THEN
    Base_Pump := TRUE;
END_IF;
END_PROGRAM