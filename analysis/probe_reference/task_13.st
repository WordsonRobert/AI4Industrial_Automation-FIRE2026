PROGRAM T13
VAR_INPUT
    Temp_Sensor : INT;
    Setpoint : INT;
END_VAR
VAR_OUTPUT
    Heater : BOOL;
END_VAR
IF Temp_Sensor < Setpoint - 5 THEN Heater := TRUE;
ELSIF Temp_Sensor > Setpoint + 5 THEN Heater := FALSE; END_IF;
END_PROGRAM
