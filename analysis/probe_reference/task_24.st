PROGRAM T24
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
END_VAR
VAR_OUTPUT
    Lamp1 : BOOL;
    Lamp2 : BOOL;
    Lamp3 : BOOL;
    Lamp4 : BOOL;
END_VAR
VAR
    Running : BOOL;
    Cyc : TON;
    Restart : BOOL;
END_VAR
Running := (Start_Button OR Running) AND NOT Stop_Button;
Cyc(IN := Running AND NOT Restart, PT := T#2s);
Restart := Cyc.Q;
Lamp1 := Running AND Cyc.ET < T#500ms;
Lamp2 := Running AND Cyc.ET >= T#500ms AND Cyc.ET < T#1s;
Lamp3 := Running AND Cyc.ET >= T#1s AND Cyc.ET < T#1500ms;
Lamp4 := Running AND Cyc.ET >= T#1500ms;
END_PROGRAM
