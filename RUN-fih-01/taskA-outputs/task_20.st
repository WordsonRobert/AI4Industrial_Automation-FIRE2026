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
    Gripper_Open : BOOL;
    Gripper_Release : BOOL;
END_VAR
VAR
    TON_Grip_Dwell : TON;
    TON_Part_Transfer : TON;
END_VAR
TON_Grip_Dwell(IN := Start_Cycle AND Part_Present AND NOT Gripper_Extended, PT := T#500ms);
TON_Part_Transfer(IN := TON_Grip_Dwell.Q AND NOT Gripper_Retracted, PT := T#1s);
Cylinder_Extend := TON_Grip_Dwell.Q;
Gripper_Close := TON_Grip_Dwell.Q;
Gripper_Open := NOT Gripper_Close;
Gripper_Release := TON_Part_Transfer.Q;
END_PROGRAM