PROGRAM T25
VAR_INPUT
    pH_Sensor : INT;
END_VAR
VAR_OUTPUT
    Acid_Pump : BOOL;
    Base_Pump : BOOL;
END_VAR
Acid_Pump := pH_Sensor > 720;
Base_Pump := pH_Sensor < 680;
END_PROGRAM
