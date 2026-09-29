PROGRAM IrrigationValveControl
VAR_INPUT
    soil_moisture : INT;
    manual_start : BOOL;
END_VAR
VAR_OUTPUT
    irrigation_valve : BOOL;
END_VAR
VAR
    TON_open : TON;
END_VAR
TON_open(IN := soil_moisture < 30 OR manual_start, PT := T#10s);
irrigation_valve := TON_open.Q AND NOT TON_open.et;
END_PROGRAM