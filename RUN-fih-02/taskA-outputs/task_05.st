PROGRAM augerMotorControl
VAR_INPUT
    High_Level_Sensor : BOOL;
    Low_Level_Sensor : BOOL;
    Auto_Mode : BOOL;
END_VAR
VAR_OUTPUT
    Auger_Motor : BOOL;
    High_Alarm : BOOL;
END_VAR
VAR
    TON_high_alarm : TON;
END_VAR
TON_high_alarm(IN := High_Level_Sensor AND NOT High_Alarm, PT := T#10s);
High_Alarm := TON_high_alarm.Q;
Auger_Motor := Low_Level_Sensor AND Auto_Mode;
END_PROGRAM