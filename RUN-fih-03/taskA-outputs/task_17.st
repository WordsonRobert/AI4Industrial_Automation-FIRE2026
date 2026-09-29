PROGRAM IrrigationControl
VAR_INPUT
    soil_moisture : INT;
    manual_start : BOOL;
END_VAR
VAR_OUTPUT
    irrigation_valve : BOOL;
END_VAR
VAR
    TON_valve : TON;
END_VAR
TON_valve(IN := soil_moisture < 30 OR manual_start, PT := T#10s);
irrigation_valve := TON_valve.Q;
END_PROGRAM