PROGRAM T08
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
    Filling : BOOL;
    Mixing : BOOL;
    T_Mix : TON;
END_VAR
IF Start_Button AND NOT Filling AND NOT Mixing AND NOT Batch_Complete THEN Filling := TRUE; END_IF;
Ingredient_A_Valve := Filling AND NOT Level_A_Full;
Ingredient_B_Valve := Filling AND NOT Level_B_Full;
IF Filling AND Level_A_Full AND Level_B_Full THEN Filling := FALSE; Mixing := TRUE; END_IF;
T_Mix(IN := Mixing, PT := T#30s);
IF T_Mix.Q THEN Mixing := FALSE; Batch_Complete := TRUE; END_IF;
Mixer_Motor := Mixing;
IF Reset_Button THEN Batch_Complete := FALSE; Filling := FALSE; Mixing := FALSE; END_IF;
END_PROGRAM
