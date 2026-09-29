PROGRAM T04
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Bottle_Present : BOOL;
    Level_Sensor : BOOL;
END_VAR
VAR_OUTPUT
    Fill_Valve : BOOL;
    Bottle_Count : INT;
END_VAR
VAR
    Running : BOOL;
    Full_Edge : R_TRIG;
END_VAR
IF Start_Button THEN Running := TRUE; END_IF;
IF Stop_Button THEN Running := FALSE; Bottle_Count := 0; END_IF;
Fill_Valve := Running AND Bottle_Present AND NOT Level_Sensor;
Full_Edge(CLK := Running AND Bottle_Present AND Level_Sensor);
IF Full_Edge.Q THEN Bottle_Count := Bottle_Count + 1; END_IF;
END_PROGRAM
