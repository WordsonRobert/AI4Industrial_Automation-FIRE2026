PROGRAM TrafficLightCycle
VAR_OUTPUT
    Red_Light : BOOL;
    Yellow_Light : BOOL;
    Green_Light : BOOL;
END_VAR
VAR
    TP_Red : TP;
    TP_Green : TP;
    TP_Yellow : TP;
END_VAR
TP_Red(IN := TRUE, PT := T#5s);
TP_Green(IN := TP_Red.Q, PT := T#5s);
TP_Yellow(IN := TP_Green.Q, PT := T#2s);
Red_Light := TP_Red.Q;
Green_Light := TP_Green.Q;
Yellow_Light := TP_Yellow.Q;
END_PROGRAM