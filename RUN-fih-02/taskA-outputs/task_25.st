PROGRAM pHControl
VAR_INPUT
    pH_Sensor : INT;
END_VAR
VAR_OUTPUT
    Acid_Pump : BOOL;
    Base_Pump : BOOL;
END_VAR
VAR
    TON_acid : TON;
    TON_base : TON;
END_VAR
TON_acid(IN := pH_Sensor > 720, PT := T#5s);
TON_base(IN := pH_Sensor < 680, PT := T#5s);
Acid_Pump := TRUE;
Base_Pump := FALSE;
IF TON_acid.Q THEN
    Acid_Pump := TRUE;
    Base_Pump := FALSE;
ELSIF TON_base.Q THEN
    Acid_Pump := FALSE;
    Base_Pump := TRUE;
END_IF;
END_PROGRAM