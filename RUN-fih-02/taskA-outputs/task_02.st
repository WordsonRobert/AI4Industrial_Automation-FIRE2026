PROGRAM traffic_light_cycle
VAR_OUTPUT
    Red_Light : BOOL;
    Yellow_Light : BOOL;
    Green_Light : BOOL;
END_VAR
VAR
    TP_Red : TP;
    TP_Yellow : TP;
    TP_Green : TP;
END_VAR
TP_Red(IN := TRUE, PT := T#5s);
TP_Yellow(IN := TRUE, PT := T#2s);
TP_Green(IN := TRUE, PT := T#5s);
Red_Light := TP_Red.Q;
Yellow_Light := TP_Yellow.Q;
Green_Light := TP_Green.Q;
END_PROGRAM