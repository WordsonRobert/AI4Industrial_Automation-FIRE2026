PROGRAM MotorControlWithFaultHandling
VAR_INPUT
    Start_Button : BOOL;
    Stop_Button : BOOL;
    Overload_Trip : BOOL;
    Reset_Button : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run : BOOL;
    Fault_Lamp : BOOL;
END_VAR
Motor_Run := Start_Button AND NOT Stop_Button;
Motor_Run := Motor_Run AND NOT Overload_Trip;
Fault_Lamp := Overload_Trip OR Fault_Lamp;
IF Reset_Button THEN
    Fault_Lamp := FALSE;
END_IF;
Motor_Run := Motor_Run AND NOT Fault_Lamp;
END_PROGRAM