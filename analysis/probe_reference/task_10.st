PROGRAM T10
VAR_INPUT
    Car_Present : BOOL;
    Start_Button : BOOL;
END_VAR
VAR_OUTPUT
    Wash_Pump : BOOL;
    Rinse_Valve : BOOL;
    Dryer_Fan : BOOL;
    Cycle_Complete : BOOL;
END_VAR
VAR
    Step : INT;
    T_Step : TON;
END_VAR
CASE Step OF
    0:
        IF Car_Present AND Start_Button THEN Step := 1; END_IF;
    1:
        T_Step(IN := TRUE, PT := T#20s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 2; END_IF;
    2:
        T_Step(IN := TRUE, PT := T#15s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 3; END_IF;
    3:
        T_Step(IN := TRUE, PT := T#10s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 4; END_IF;
    4:
        IF NOT Car_Present THEN Step := 0; END_IF;
END_CASE;
Wash_Pump := Step = 1;
Rinse_Valve := Step = 2;
Dryer_Fan := Step = 3;
Cycle_Complete := Step = 4;
END_PROGRAM
