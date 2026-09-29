PROGRAM PartDetectionAndInspection
VAR_INPUT
    Part_Detect : BOOL;
    Part_Good : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Cylinder : BOOL;
END_VAR
VAR
    TON_Reject : TON;
END_VAR
TON_Reject(IN := NOT Part_Good, PT := T#500ms);
Reject_Cylinder := TON_Reject.Q;
END_PROGRAM