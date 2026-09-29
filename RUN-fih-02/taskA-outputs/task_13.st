PROGRAM HeatControl
VAR_INPUT
    Temp_Sensor : INT;
    Setpoint : INT;
END_VAR
VAR_OUTPUT
    Heater : BOOL;
END_VAR
VAR
    last_temp : INT;
    TON_heater_on : TON;
    TON_heater_off : TON;
END_VAR
TON_heater_on.et := Temp_Sensor - last_temp;
last_temp := Temp_Sensor;
TON_heater_on(IN := TON_heater_on.et <= 5, PT := T#1s);
TON_heater_off(IN := TON_heater_on.et >= 5, PT := T#1s);
IF TON_heater_on.Q THEN
    Heater := TRUE;
ELSIF TON_heater_off.Q THEN
    Heater := FALSE;
END_IF;
Heater := Heater AND (Temp_Sensor <= Setpoint + 5 OR Temp_Sensor >= Setpoint - 5);
END_PROGRAM