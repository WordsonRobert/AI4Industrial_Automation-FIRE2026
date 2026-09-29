PROGRAM PartDetect
VAR_INPUT
    Part_Detect : BOOL;
    Part_Good : BOOL;
END_VAR
VAR_OUTPUT
    Reject_Cylinder : BOOL;
END_VAR
VAR
    TON0 : TON;
END_VAR
TON0(IN := Part_Detect, PT := T#2s);
Reject_Cylinder := TON0.Q;
END_PROGRAM