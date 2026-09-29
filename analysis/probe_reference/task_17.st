PROGRAM T17
VAR_INPUT
    Soil_Moisture : INT;
    Manual_Start : BOOL;
END_VAR
VAR_OUTPUT
    Irrigation_Valve : BOOL;
END_VAR
VAR
    Hold : TP;
END_VAR
Hold(IN := Soil_Moisture < 30 OR Manual_Start, PT := T#10m);
Irrigation_Valve := Hold.Q;
END_PROGRAM
