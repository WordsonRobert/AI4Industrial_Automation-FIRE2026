"""Hand-written reference ST programs, used ONLY to validate that every
behavioural probe in probes.py is satisfiable by a correct program.
They are not the organisers' references and were never used for training
or submission. Writes task_NN.st next to this file."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def prog(name, ins, outs, locs, body):
    def block(kw, decls):
        if not decls:
            return ""
        return kw + "\n" + "".join(f"    {n} : {t};\n" for n, t in decls) + "END_VAR\n"
    return (f"PROGRAM {name}\n" + block("VAR_INPUT", ins) + block("VAR_OUTPUT", outs)
            + block("VAR", locs) + body.strip() + "\nEND_PROGRAM\n")


B = "BOOL"
R = {}

R[1] = prog("T01", [("Low_Level_Sensor", B), ("High_Level_Sensor", B), ("Start_Button", B), ("Stop_Button", B)],
            [("Fill_Pump", B)], [], """
Fill_Pump := ((Start_Button AND NOT Low_Level_Sensor) OR Fill_Pump) AND NOT High_Level_Sensor AND NOT Stop_Button;
""")

R[2] = prog("T02", [], [("Red_Light", B), ("Yellow_Light", B), ("Green_Light", B)],
            [("Cyc", "TON"), ("Restart", B)], """
Cyc(IN := NOT Restart, PT := T#12s);
Restart := Cyc.Q;
Red_Light := Cyc.ET < T#5s;
Green_Light := Cyc.ET >= T#5s AND Cyc.ET < T#10s;
Yellow_Light := Cyc.ET >= T#10s;
""")


def fault(name, trip, lamp):
    return prog(name, [("Start_Button", B), ("Stop_Button", B), (trip, B), ("Reset_Button", B)],
                [("Motor_Run", B), (lamp, B)], [], f"""
IF {trip} THEN
    {lamp} := TRUE;
ELSIF Reset_Button THEN
    {lamp} := FALSE;
END_IF;
Motor_Run := (Start_Button OR Motor_Run) AND NOT Stop_Button AND NOT {lamp};
""")


R[3] = fault("T03", "Overload_Trip", "Fault_Lamp")
R[6] = fault("T06", "E_Stop", "EStop_Lamp")

R[4] = prog("T04", [("Start_Button", B), ("Stop_Button", B), ("Bottle_Present", B), ("Level_Sensor", B)],
            [("Fill_Valve", B), ("Bottle_Count", "INT")], [("Running", B), ("Full_Edge", "R_TRIG")], """
IF Start_Button THEN Running := TRUE; END_IF;
IF Stop_Button THEN Running := FALSE; Bottle_Count := 0; END_IF;
Fill_Valve := Running AND Bottle_Present AND NOT Level_Sensor;
Full_Edge(CLK := Running AND Bottle_Present AND Level_Sensor);
IF Full_Edge.Q THEN Bottle_Count := Bottle_Count + 1; END_IF;
""")

R[5] = prog("T05", [("Low_Level_Sensor", B), ("High_Level_Sensor", B), ("Auto_Mode", B)],
            [("Auger_Motor", B), ("High_Alarm", B)], [("T_High", "TON")], """
Auger_Motor := Auto_Mode AND Low_Level_Sensor AND NOT High_Level_Sensor;
T_High(IN := High_Level_Sensor, PT := T#10s);
High_Alarm := T_High.Q;
""")

R[7] = prog("T07", [("Start_Button", B), ("Stop_Button", B), ("Speed_Select", B), ("Low_Speed_Set", "INT"), ("High_Speed_Set", "INT")],
            [("Conveyor_Speed", "INT"), ("Running_Lamp", B)], [("Running", B)], """
Running := (Start_Button OR Running) AND NOT Stop_Button;
IF NOT Running THEN
    Conveyor_Speed := 0;
ELSIF Speed_Select THEN
    Conveyor_Speed := High_Speed_Set;
ELSE
    Conveyor_Speed := Low_Speed_Set;
END_IF;
Running_Lamp := Running;
""")

R[8] = prog("T08", [("Start_Button", B), ("Reset_Button", B), ("Level_A_Full", B), ("Level_B_Full", B)],
            [("Ingredient_A_Valve", B), ("Ingredient_B_Valve", B), ("Mixer_Motor", B), ("Batch_Complete", B)],
            [("Filling", B), ("Mixing", B), ("T_Mix", "TON")], """
IF Start_Button AND NOT Filling AND NOT Mixing AND NOT Batch_Complete THEN Filling := TRUE; END_IF;
Ingredient_A_Valve := Filling AND NOT Level_A_Full;
Ingredient_B_Valve := Filling AND NOT Level_B_Full;
IF Filling AND Level_A_Full AND Level_B_Full THEN Filling := FALSE; Mixing := TRUE; END_IF;
T_Mix(IN := Mixing, PT := T#30s);
IF T_Mix.Q THEN Mixing := FALSE; Batch_Complete := TRUE; END_IF;
Mixer_Motor := Mixing;
IF Reset_Button THEN Batch_Complete := FALSE; Filling := FALSE; Mixing := FALSE; END_IF;
""")

R[9] = prog("T09", [("Open_Button", B), ("Close_Button", B), ("Open_Limit", B), ("Closed_Limit", B), ("Obstacle_Sensor", B)],
            [("Door_Motor_Open", B), ("Door_Motor_Close", B)], [], """
IF Door_Motor_Close AND Obstacle_Sensor THEN
    Door_Motor_Close := FALSE;
    Door_Motor_Open := TRUE;
END_IF;
IF Open_Button AND NOT Door_Motor_Close THEN Door_Motor_Open := TRUE; END_IF;
IF Close_Button AND NOT Door_Motor_Open THEN Door_Motor_Close := TRUE; END_IF;
IF Open_Limit THEN Door_Motor_Open := FALSE; END_IF;
IF Closed_Limit THEN Door_Motor_Close := FALSE; END_IF;
""")

R[10] = prog("T10", [("Car_Present", B), ("Start_Button", B)],
             [("Wash_Pump", B), ("Rinse_Valve", B), ("Dryer_Fan", B), ("Cycle_Complete", B)],
             [("Step", "INT"), ("T_Step", "TON")], """
CASE Step OF
    0:
        IF Car_Present AND Start_Button THEN Step := 1; END_IF;
    1:
        T_Step(IN := TRUE, PT := T#20s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 2; END_IF;
    2:
        T_Step(IN := TRUE, PT := T#15s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 3; END_IF;
    3:
        T_Step(IN := TRUE, PT := T#10s);
        IF T_Step.Q THEN T_Step(IN := FALSE); Step := 4; END_IF;
    4:
        IF NOT Car_Present THEN Step := 0; END_IF;
END_CASE;
Wash_Pump := Step = 1;
Rinse_Valve := Step = 2;
Dryer_Fan := Step = 3;
Cycle_Complete := Step = 4;
""")

R[11] = prog("T11", [("Box_Sensor", B)], [("Pusher_Cylinder", B), ("Box_Count_Display", "INT")],
             [("Cnt", "CTU"), ("Push", "TP")], """
Cnt(CU := Box_Sensor, R := Cnt.Q, PV := 5);
Push(IN := Cnt.Q, PT := T#1s);
Cnt(CU := Box_Sensor, R := Cnt.Q, PV := 5);
Pusher_Cylinder := Push.Q;
Box_Count_Display := Cnt.CV;
""")

R[12] = prog("T12", [("Weight_Input", "INT"), ("Target_Weight", "INT"), ("Photo_Eye", B)], [("Reject_Pusher", B)],
             [("Trig", "R_TRIG"), ("Pulse", "TP")], """
Trig(CLK := Photo_Eye);
Pulse(IN := Trig.Q AND ABS(Weight_Input - Target_Weight) > 5, PT := T#500ms);
Reject_Pusher := Pulse.Q;
""")

R[13] = prog("T13", [("Temp_Sensor", "INT"), ("Setpoint", "INT")], [("Heater", B)], [], """
IF Temp_Sensor < Setpoint - 5 THEN Heater := TRUE;
ELSIF Temp_Sensor > Setpoint + 5 THEN Heater := FALSE; END_IF;
""")

R[14] = prog("T14", [("Temp_Sensor", "INT")], [("Fan1", B), ("Fan2", B)], [], """
IF Temp_Sensor > 300 THEN Fan1 := TRUE; ELSIF Temp_Sensor < 280 THEN Fan1 := FALSE; END_IF;
IF Temp_Sensor > 350 THEN Fan2 := TRUE; ELSIF Temp_Sensor < 330 THEN Fan2 := FALSE; END_IF;
""")

R[15] = prog("T15", [("Pressure_Sensor", "INT")], [("Compressor_Motor", B)], [], """
IF Pressure_Sensor < 80 THEN Compressor_Motor := TRUE;
ELSIF Pressure_Sensor > 120 THEN Compressor_Motor := FALSE; END_IF;
""")

R[16] = prog("T16", [("CO2_Sensor", "INT")], [("Damper_Position", "INT")], [], """
IF CO2_Sensor <= 600 THEN Damper_Position := 0;
ELSIF CO2_Sensor >= 1000 THEN Damper_Position := 100;
ELSE Damper_Position := (CO2_Sensor - 600) * 100 / 400; END_IF;
""")

R[17] = prog("T17", [("Soil_Moisture", "INT"), ("Manual_Start", B)], [("Irrigation_Valve", B)], [("Hold", "TP")], """
Hold(IN := Soil_Moisture < 30 OR Manual_Start, PT := T#10m);
Irrigation_Valve := Hold.Q;
""")

R[18] = prog("T18", [("Part_Detect", B), ("Part_Good", B)], [("Reject_Cylinder", B)], [("Trig", "R_TRIG"), ("Pulse", "TP")], """
Trig(CLK := Part_Detect);
Pulse(IN := Trig.Q AND NOT Part_Good, PT := T#500ms);
Reject_Cylinder := Pulse.Q;
""")

R[19] = prog("T19", [("Call_Floor1", B), ("Call_Floor2", B), ("At_Floor1", B), ("At_Floor2", B)],
             [("Motor_Up", B), ("Motor_Down", B)], [], """
Motor_Up := ((Call_Floor2 AND NOT At_Floor2) OR Motor_Up) AND NOT At_Floor2 AND NOT Motor_Down;
Motor_Down := ((Call_Floor1 AND NOT At_Floor1) OR Motor_Down) AND NOT At_Floor1 AND NOT Motor_Up;
""")

R[20] = prog("T20", [("Start_Cycle", B), ("Part_Present", B), ("Gripper_Extended", B), ("Gripper_Retracted", B)],
             [("Cylinder_Extend", B), ("Gripper_Close", B)], [("Step", "INT"), ("Dwell", "TON")], """
CASE Step OF
    0:
        IF Start_Cycle AND Part_Present THEN Step := 1; END_IF;
    1:
        IF Gripper_Extended THEN Step := 2; END_IF;
    2:
        Dwell(IN := TRUE, PT := T#500ms);
        IF Dwell.Q THEN Dwell(IN := FALSE); Step := 3; END_IF;
    3:
        IF Gripper_Retracted THEN Step := 0; END_IF;
END_CASE;
Cylinder_Extend := Step = 1 OR Step = 2;
Gripper_Close := Step = 2 OR Step = 3;
IF Step = 3 AND Gripper_Retracted THEN Gripper_Close := FALSE; END_IF;
IF Step = 0 THEN Gripper_Close := FALSE; END_IF;
""")

R[21] = prog("T21", [("Start_Button", B), ("Stop_Button", B), ("Light_Curtain_Clear", B)],
             [("Conveyor_Run", B), ("Safety_Fault_Lamp", B)], [], """
Conveyor_Run := (Start_Button OR Conveyor_Run) AND NOT Stop_Button AND Light_Curtain_Clear;
Safety_Fault_Lamp := NOT Light_Curtain_Clear;
""")

R[22] = prog("T22", [("Start_Button", B), ("Stop_Button", B), ("Entry_Photo_Eye", B), ("Exit_Photo_Eye", B)],
             [("Conveyor_Run", B), ("Jam_Alarm", B)], [("T_Jam", "TON")], """
T_Jam(IN := Entry_Photo_Eye AND NOT Exit_Photo_Eye, PT := T#8s);
IF T_Jam.Q THEN Jam_Alarm := TRUE; END_IF;
IF Stop_Button THEN Jam_Alarm := FALSE; END_IF;
Conveyor_Run := (Start_Button OR Conveyor_Run) AND NOT Stop_Button AND NOT Jam_Alarm;
""")

R[23] = prog("T23", [("Start_Button", B), ("Stop_Button", B), ("Flow_A_Pulse", B)],
             [("Valve_A", B), ("Valve_B", B)], [("Running", B), ("Cnt", "CTU")], """
Running := (Start_Button OR Running) AND NOT Stop_Button;
Valve_A := Running;
Cnt(CU := Flow_A_Pulse AND Running, R := Cnt.Q AND NOT Flow_A_Pulse, PV := 4);
Valve_B := Running AND Cnt.Q;
""")

R[24] = prog("T24", [("Start_Button", B), ("Stop_Button", B)],
             [("Lamp1", B), ("Lamp2", B), ("Lamp3", B), ("Lamp4", B)], [("Running", B), ("Cyc", "TON"), ("Restart", B)], """
Running := (Start_Button OR Running) AND NOT Stop_Button;
Cyc(IN := Running AND NOT Restart, PT := T#2s);
Restart := Cyc.Q;
Lamp1 := Running AND Cyc.ET < T#500ms;
Lamp2 := Running AND Cyc.ET >= T#500ms AND Cyc.ET < T#1s;
Lamp3 := Running AND Cyc.ET >= T#1s AND Cyc.ET < T#1500ms;
Lamp4 := Running AND Cyc.ET >= T#1500ms;
""")

R[25] = prog("T25", [("pH_Sensor", "INT")], [("Acid_Pump", B), ("Base_Pump", B)], [], """
Acid_Pump := pH_Sensor > 720;
Base_Pump := pH_Sensor < 680;
""")

R[26] = prog("T26", [("Start_Button", B), ("Stop_Button", B)], [("Conveyor_Run", B)], [], """
Conveyor_Run := (Start_Button OR Conveyor_Run) AND NOT Stop_Button;
""")


def rpm(name, extra_in, extra_out, display):
    ins = [("RPM_Set", "INT"), ("Start_Button", B), ("Stop_Button", B)] + extra_in
    outs = [("Conveyor_Run", "INT"), ("start_light", B)] + extra_out
    body = """
start_light := (Start_Button OR start_light) AND NOT Stop_Button;
IF start_light THEN Conveyor_Run := RPM_Set; ELSE Conveyor_Run := 0; END_IF;
"""
    if display:
        body += "Digital_Display := RPM_Set;\n"
    return prog(name, ins, outs, [], body)


R[27] = rpm("T27", [], [], False)
R[28] = prog("T28", [("RPM_Set", "INT"), ("Start_Button", B), ("Stop_Button", B)],
             [("Digital_Display", "INT"), ("Conveyor_Run", "INT")], [("Running", B)], """
Running := (Start_Button OR Running) AND NOT Stop_Button;
IF Running THEN Conveyor_Run := RPM_Set; ELSE Conveyor_Run := 0; END_IF;
Digital_Display := RPM_Set;
""")
R[29] = rpm("T29", [("Vision_Sensor", "INT")], [("Digital_Display", "INT"), ("display_box_counter", "INT")], True)
R[30] = rpm("T30", [("Vision_Sensor", "INT")], [("Digital_Display", "INT"), ("display_box_counter", "INT"),
            ("blue_box_counter", "INT"), ("grey_box_counter", "INT"), ("green_box_counter", "INT")], True)

if __name__ == "__main__":
    for k, v in R.items():
        with open(os.path.join(HERE, f"task_{k:02d}.st"), "w") as f:
            f.write(v)
    print(f"wrote {len(R)} reference programs")
