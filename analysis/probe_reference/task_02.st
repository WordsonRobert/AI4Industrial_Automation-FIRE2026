PROGRAM T02
VAR_OUTPUT
    Red_Light : BOOL;
    Yellow_Light : BOOL;
    Green_Light : BOOL;
END_VAR
VAR
    Cyc : TON;
    Restart : BOOL;
END_VAR
Cyc(IN := NOT Restart, PT := T#12s);
Restart := Cyc.Q;
Red_Light := Cyc.ET < T#5s;
Green_Light := Cyc.ET >= T#5s AND Cyc.ET < T#10s;
Yellow_Light := Cyc.ET >= T#10s;
END_PROGRAM
