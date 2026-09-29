PROGRAM CycleControl
VAR_INPUT
    Start_Cycle : BOOL;
    Part_Present : BOOL;
END_VAR
VAR_OUTPUT
    Gripper_Extended : BOOL;
    Gripper_Close : BOOL;
    Cylinder_Extend : BOOL;
END_VAR
VAR
    cycle_start : BOOL;
    grip_close : BOOL;
    wait_ms : TON;
END_VAR
cycle_start := Start_Cycle AND Part_Present;
grip_close := cycle_start AND Gripper_Extended;
IF grip_close THEN
    Gripper_Close := TRUE;
    wait_ms(IN := T#500ms);
    Gripper_Close := FALSE;
    Gripper_Extended := FALSE;
    Cylinder_Extend := FALSE;
END_IF;
Gripper_Extended := cycle_start OR grip_close;
Cylinder_Extend := cycle_start;
wait_ms(IN := wait_ms.Q);
END_PROGRAM