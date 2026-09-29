PROGRAM SiloControl
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
    TON_High : TON;
END_VAR
TON_High(IN := High_Level_Sensor AND NOT Low_Level_Sensor, PT := T#10s);
Auger_Motor := Auto_Mode AND NOT High_Level_Sensor;
High_Alarm := TON_High.Q;
END_PROGRAM