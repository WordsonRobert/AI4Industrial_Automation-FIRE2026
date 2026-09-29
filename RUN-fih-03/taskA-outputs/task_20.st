PROGRAM CycleControl
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
    TON_Grip_Dwell : TON;
END_VAR
TON_Grip_Dwell(IN := Start_Cycle AND Part_Present AND NOT Gripper_Extended, PT := T#500ms);
Cylinder_Extend := TON_Grip_Dwell.Q;
Gripper_Close := TON_Grip_Dwell.Q;
END_PROGRAM