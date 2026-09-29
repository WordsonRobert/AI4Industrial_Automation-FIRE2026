PROGRAM T16
VAR_INPUT
    CO2_Sensor : INT;
END_VAR
VAR_OUTPUT
    Damper_Position : INT;
END_VAR
IF CO2_Sensor <= 600 THEN Damper_Position := 0;
ELSIF CO2_Sensor >= 1000 THEN Damper_Position := 100;
ELSE Damper_Position := (CO2_Sensor - 600) * 100 / 400; END_IF;
END_PROGRAM
