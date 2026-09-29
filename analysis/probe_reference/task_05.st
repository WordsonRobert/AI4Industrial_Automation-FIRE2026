PROGRAM T05
VAR_INPUT
    Low_Level_Sensor : BOOL;
    High_Level_Sensor : BOOL;
    Auto_Mode : BOOL;
END_VAR
VAR_OUTPUT
    Auger_Motor : BOOL;
    High_Alarm : BOOL;
END_VAR
VAR
    T_High : TON;
END_VAR
Auger_Motor := Auto_Mode AND Low_Level_Sensor AND NOT High_Level_Sensor;
T_High(IN := High_Level_Sensor, PT := T#10s);
High_Alarm := T_High.Q;
END_PROGRAM
