PROGRAM MultiValveCycle
VAR_INPUT
    Start_Button : BOOL;
    Reset_Button : BOOL;
    Level_A_Full : BOOL;
    Level_B_Full : BOOL;
END_VAR
VAR_OUTPUT
    Ingredient_A_Valve : BOOL;
    Ingredient_B_Valve : BOOL;
    Mixer_Motor : BOOL;
    Batch_Complete : BOOL;
END_VAR
VAR
    TON_Mixing : TON;
    scaled_level_a : REAL;
    scaled_level_b : REAL;
END_VAR
scaled_level_a := Level_A_Full / 50.0;
scaled_level_b := Level_B_Full / 50.0;
Ingredient_A_Valve := scaled_level_a >= 49.0 AND NOT Batch_Complete;
Ingredient_B_Valve := scaled_level_b >= 49.0 AND NOT Batch_Complete;
TON_Mixing(IN := Start_Button AND NOT Batch_Complete OR Reset_Button, PT := T#30s);
Mixer_Motor := TON_Mixing.Q;
Batch_Complete := Mixer_Motor OR Reset_Button;
END_PROGRAM