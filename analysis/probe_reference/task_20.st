PROGRAM T20
VAR_INPUT
    Start_Cycle : BOOL;
    Part_Present : BOOL;
    Gripper_Extended : BOOL;
    Gripper_Retracted : BOOL;
END_VAR
VAR_OUTPUT
    Cylinder_Extend : BOOL;
    Gripper_Close : BOOL;
END_VAR
VAR
    Step : INT;
    Dwell : TON;
END_VAR
CASE Step OF
    0:
        IF Start_Cycle AND Part_Present THEN Step := 1; END_IF;
    1:
        IF Gripper_Extended THEN Step := 2; END_IF;
    2:
        Dwell(IN := TRUE, PT := T#500ms);
        IF Dwell.Q THEN Dwell(IN := FALSE); Step := 3; END_IF;
    3:
        IF Gripper_Retracted THEN Step := 0; END_IF;
END_CASE;
Cylinder_Extend := Step = 1 OR Step = 2;
Gripper_Close := Step = 2 OR Step = 3;
IF Step = 3 AND Gripper_Retracted THEN Gripper_Close := FALSE; END_IF;
IF Step = 0 THEN Gripper_Close := FALSE; END_IF;
END_PROGRAM
