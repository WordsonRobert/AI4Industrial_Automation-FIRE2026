PROGRAM DamperControl
VAR_INPUT
    CO2_Sensor : INT;
END_VAR
VAR_OUTPUT
    Damper_Position : REAL;
END_VAR
Damper_Position := (CO2_Sensor - 600) / 400.0 * 100.0 + 50.0;
END_PROGRAM