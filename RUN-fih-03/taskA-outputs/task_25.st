PROGRAM PHControl
VAR_INPUT
    pH_Sensor : INT;
END_VAR
VAR_OUTPUT
    Acid_Pump : BOOL;
    Base_Pump : BOOL;
END_VAR
pH_Sensor := REAL_TO_INT(Scaled_PHSensor / 100.0);
Scaled_PHSensor := PH_Sensor * 0.01;
IF Scaled_PHSensor > 720.0 THEN
    Acid_Pump := TRUE;
ELSIF Scaled_PHSensor < 680.0 THEN
    Base_Pump := TRUE;
END_IF;
Acid_Pump := FALSE;
Base_Pump := FALSE;
END_PROGRAM