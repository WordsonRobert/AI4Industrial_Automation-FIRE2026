PROGRAM DamperControl
VAR_INPUT
    CO2_Sensor : INT;
END_VAR
VAR_OUTPUT
    Damper_Position : INT;
END_VAR
VAR
    TON_open : TON;
    TON_close : TON;
END_VAR
TON_open(IN := CO2_Sensor >= 1000, PT := T#10s);
TON_close(IN := CO2_Sensor <= 600, PT := T#10s);
IF TON_open.Q THEN
    Damper_Position := 100;
ELSIF TON_close.Q THEN
    Damper_Position := 0;
END_IF;
Damper_Position := Damper_Position + (CO2_Sensor - 600) / 400 * 2;
END_PROGRAM