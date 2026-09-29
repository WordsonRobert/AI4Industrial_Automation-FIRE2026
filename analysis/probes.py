"""
probes.py -- behavioural probes for the 30 FIRE 2026 NL2PLC test tasks.

Each probe drives the named inputs of a submitted ST program through a
short scenario (with st_sim.py, 20 ms scan, absolute clock) and checks
only behaviour that the task text states explicitly. Buttons are
momentary and normally open (TRUE = pressed); photo-eyes read TRUE when
blocked. Checks were written from the task statements alone; outputs the text
names but never describes (e.g. Running_Lamp, start_light) are not checked.
Word outputs named after the actuator (Conveyor_Run: %QW...) are taken to
carry the set-point while running (tasks 27-30).

Every check records the outputs it inspects, so the analysis can refuse
credit for an output that is on where the task requires it to be off.

A program that does not declare an input under the task's name cannot be
driven, and a missing output reads as "absent", which fails any check on
it. Identifiers are matched case-insensitively (IEC 61131-3 rule).
"""

SCAN = 20


class Harness:
    def __init__(self, prog):
        self.p = prog
        self.t = 0
        self.inputs = {}
        self.checks = []
        self.rec = None
        drivable = {k for k, s in prog.section.items() if s in ("VAR_INPUT", "VAR_IN_OUT")}
        self.drivable = drivable
        self.readable = {k for k, s in prog.section.items() if s in ("VAR_OUTPUT", "VAR_IN_OUT")}

    # -- stimulus
    def set(self, **kw):
        for k, v in kw.items():
            self.inputs[k.lower()] = v

    def run(self, ms):
        end = self.t + ms
        while self.t < end:
            self.p.scan({k: v for k, v in self.inputs.items() if k in self.drivable}, self.t)
            if self.rec is not None:
                self.rec.append((self.t, {n: self.out(n) for n in self.rec_names}))
            self.t += SCAN

    def until(self, t_abs):
        if t_abs > self.t:
            self.run(t_abs - self.t)

    def pulse(self, name, on=200, after=300):
        self.set(**{name: True})
        self.run(on)
        self.set(**{name: False})
        self.run(after)

    # -- observation
    def out(self, name):
        k = name.lower()
        if k not in self.readable:
            return None
        return self.p.vars.get(k)

    @staticmethod
    def match(actual, expected, tol):
        if actual is None:
            return False
        if isinstance(expected, bool):
            return bool(actual) == expected
        try:
            return abs(float(actual) - float(expected)) <= tol
        except (TypeError, ValueError):
            return False

    def expect(self, label, tol=0, **outs):
        ok = all(self.match(self.out(n), v, tol) for n, v in outs.items())
        self.checks.append((label, ok, sorted(outs)))
        return ok

    def hold(self, label, ms, tol=0, **outs):
        """Run for ms and require the outputs to match at every scan."""
        ok = True
        end = self.t + ms
        while self.t < end:
            self.run(SCAN)
            ok = ok and all(self.match(self.out(n), v, tol) for n, v in outs.items())
        self.checks.append((label, ok, sorted(outs)))
        return ok

    def pulse_hold(self, label, name, on, after, **outs):
        """Pulse an input and require the outputs to match throughout."""
        self.set(**{name: True})
        ok = True
        for dur, val in ((on, True), (after, False)):
            self.set(**{name: val})
            end = self.t + dur
            while self.t < end:
                self.run(SCAN)
                ok = ok and all(self.match(self.out(n), v, 0) for n, v in outs.items())
        self.checks.append((label, ok, sorted(outs)))
        return ok

    def check(self, label, ok, outs):
        self.checks.append((label, bool(ok), sorted(outs)))

    def start_record(self, *names):
        self.rec, self.rec_names = [], names

    def stop_record(self):
        r, self.rec = self.rec, None
        return r


def rising_edges(rec, name):
    n, prev = 0, False
    for _, vals in rec:
        v = bool(vals[name])
        if v and not prev:
            n += 1
        prev = v
    return n


# --------------------------------------------------------------- probes
LATCH = 2000   # a latched output must stay on for this long after the press


def t01(h):
    h.run(200)
    h.expect("idle: pump off", Fill_Pump=False)
    h.pulse("Start_Button")
    h.hold("start latches pump", LATCH, Fill_Pump=True)
    h.set(High_Level_Sensor=True); h.run(200)
    h.expect("high level stops pump", Fill_Pump=False)
    h.set(High_Level_Sensor=False); h.run(200)
    h.expect("no restart without start", Fill_Pump=False)
    h.pulse("Start_Button"); h.pulse("Stop_Button")
    h.expect("stop button stops pump", Fill_Pump=False)
    h.set(Stop_Button=True, Start_Button=True); h.run(200)
    h.expect("stop overrides start", Fill_Pump=False)
    h.set(Stop_Button=False, Start_Button=False); h.run(200)
    h.set(Low_Level_Sensor=True); h.pulse("Start_Button")
    h.expect("no start while low-level sensor active", Fill_Pump=False)


def t02(h):
    lamps = ("Red_Light", "Green_Light", "Yellow_Light")

    def only(on):
        return {n: (n == on) for n in lamps}
    for t, lamp, label in [(2500, "Red_Light", "red phase"), (7500, "Green_Light", "green phase"),
                           (11000, "Yellow_Light", "yellow phase"), (14500, "Red_Light", "cycle repeats (red)"),
                           (19500, "Green_Light", "cycle repeats (green)")]:
        h.until(t)
        h.expect(label, **only(lamp))


def _latched_fault(h, trip, lamp):
    h.run(200)
    h.pulse("Start_Button")
    h.hold("start latches motor", LATCH, Motor_Run=True)
    h.pulse("Stop_Button")
    h.expect("stop button stops motor", Motor_Run=False)
    h.pulse("Start_Button")
    h.set(**{trip: True}); h.run(200)
    h.expect("trip stops motor", Motor_Run=False)
    h.expect("trip sets fault lamp", **{lamp: True})
    h.set(**{trip: False}); h.run(200)
    h.hold("fault stays latched", 1000, **{lamp: True})
    h.set(**{trip: True}); h.run(100); h.pulse("Reset_Button")
    h.expect("reset ignored while trip active", **{lamp: True})
    h.set(**{trip: False}); h.run(200); h.pulse("Reset_Button")
    h.expect("reset clears fault", **{lamp: False})
    h.pulse("Start_Button")
    h.hold("restart after reset", LATCH, Motor_Run=True)


def t03(h):
    _latched_fault(h, "Overload_Trip", "Fault_Lamp")


def t04(h):
    h.set(Bottle_Present=True); h.run(200)
    h.expect("valve closed before cycle start", Fill_Valve=False)
    h.pulse("Start_Button")
    h.expect("valve opens: bottle present, not full", Fill_Valve=True)
    h.set(Level_Sensor=True); h.run(200)
    h.expect("valve closes when full", Fill_Valve=False)
    h.set(Bottle_Present=False); h.run(200); h.set(Level_Sensor=False); h.run(200)
    h.expect("count = 1 after first bottle", Bottle_Count=1)
    h.set(Bottle_Present=True); h.run(200)
    h.expect("valve reopens for next bottle", Fill_Valve=True)
    h.set(Level_Sensor=True); h.run(200); h.set(Bottle_Present=False); h.run(200); h.set(Level_Sensor=False); h.run(200)
    h.expect("count = 2 after second bottle", Bottle_Count=2)
    h.pulse("Stop_Button")
    h.expect("stop resets counter", Bottle_Count=0)
    h.set(Bottle_Present=True); h.run(200)
    h.expect("valve closed after stop", Fill_Valve=False)


def t05(h):
    h.set(Auto_Mode=True, Low_Level_Sensor=True); h.run(200)
    h.expect("auger runs in auto at low level", Auger_Motor=True)
    h.set(Auto_Mode=False); h.run(200)
    h.expect("auger off outside auto mode", Auger_Motor=False)
    h.set(Auto_Mode=True); h.run(200)
    h.set(Low_Level_Sensor=False, High_Level_Sensor=True); t0 = h.t; h.run(200)
    h.expect("auger stops at high level", Auger_Motor=False)
    h.until(t0 + 9000)
    h.expect("no alarm before 10 s at high level", High_Alarm=False)
    h.until(t0 + 11000)
    h.expect("alarm after 10 s at high level", High_Alarm=True)


def t06(h):
    _latched_fault(h, "E_Stop", "EStop_Lamp")


def t07(h):
    h.set(Low_Speed_Set=100, High_Speed_Set=300); h.run(200)
    h.expect("speed zero when stopped", Conveyor_Speed=0)
    h.pulse("Start_Button")
    h.hold("low speed when select off", 1000, Conveyor_Speed=100)
    h.set(Speed_Select=True); h.run(200)
    h.expect("high speed when select on", Conveyor_Speed=300)
    h.pulse("Stop_Button")
    h.expect("speed zero after stop", Conveyor_Speed=0)


def t08(h):
    h.run(200)
    h.pulse("Start_Button")
    h.hold("start opens both valves", 1000, Ingredient_A_Valve=True, Ingredient_B_Valve=True)
    h.set(Level_A_Full=True); h.run(200)
    h.expect("valve A closes on its own level", Ingredient_A_Valve=False, Ingredient_B_Valve=True)
    h.set(Level_B_Full=True); t0 = h.t; h.run(200)
    h.expect("valve B closes and mixer starts", Ingredient_B_Valve=False, Mixer_Motor=True)
    h.until(t0 + 28000)
    h.expect("mixer still running before 30 s", Mixer_Motor=True, Batch_Complete=False)
    h.until(t0 + 31000)
    h.expect("mixer stops after 30 s", Mixer_Motor=False)
    h.expect("batch complete after mixing", Batch_Complete=True)


def t09(h):
    h.run(200)
    h.pulse("Open_Button")
    h.hold("open button latches opening", 1000, Door_Motor_Open=True)
    h.set(Open_Limit=True); h.run(200)
    h.expect("open limit stops opening", Door_Motor_Open=False)
    h.pulse("Close_Button")
    h.set(Open_Limit=False)
    h.hold("close button latches closing", 1000, Door_Motor_Close=True)
    h.pulse("Obstacle_Sensor")
    h.expect("obstacle while closing reverses door", Door_Motor_Close=False, Door_Motor_Open=True)
    h.set(Open_Limit=True); h.run(200)
    h.expect("reopening stops at open limit", Door_Motor_Open=False)
    h.pulse("Close_Button")
    h.set(Open_Limit=False); h.run(300)
    h.set(Closed_Limit=True); h.run(200)
    h.expect("closed limit stops closing", Door_Motor_Close=False)


def t10(h):
    h.set(Car_Present=True); h.run(200)
    t0 = h.t
    h.pulse("Start_Button")
    h.expect("wash runs first", Wash_Pump=True, Rinse_Valve=False, Dryer_Fan=False)
    h.until(t0 + 19000)
    h.expect("wash still on at 19 s", Wash_Pump=True, Rinse_Valve=False)
    h.until(t0 + 21000)
    h.expect("rinse follows 20 s wash", Wash_Pump=False, Rinse_Valve=True)
    h.until(t0 + 34000)
    h.expect("rinse still on at 34 s", Rinse_Valve=True, Dryer_Fan=False)
    h.until(t0 + 36000)
    h.expect("dryer follows 15 s rinse", Rinse_Valve=False, Dryer_Fan=True)
    h.until(t0 + 46000)
    h.expect("cycle complete after 10 s drying", Dryer_Fan=False, Cycle_Complete=True)
    h.set(Car_Present=False); h.run(300)
    h.expect("complete resets when car leaves", Cycle_Complete=False)


def t11(h):
    def box():
        h.pulse("Box_Sensor", on=150, after=150)
    h.run(200)
    for _ in range(3):
        box()
    h.expect("display counts boxes", Box_Count_Display=3)
    h.expect("no push before 5 boxes", Pusher_Cylinder=False)
    box(); box()
    h.expect("pusher fires on 5th box", Pusher_Cylinder=True)
    h.run(1200)
    h.expect("pusher pulse ends after 1 s", Pusher_Cylinder=False)
    h.expect("count resets after push", Box_Count_Display=0)
    box(); box()
    h.expect("counting restarts from zero", Box_Count_Display=2)
    h.expect("no extra push", Pusher_Cylinder=False)


def t12(h):
    h.set(Target_Weight=100, Weight_Input=103); h.run(200)
    h.pulse_hold("in-tolerance part not rejected", "Photo_Eye", 100, 900, Reject_Pusher=False)
    h.set(Weight_Input=110)
    h.hold("no reject without photo-eye trigger", 1000, Reject_Pusher=False)
    h.pulse("Photo_Eye", on=100, after=100)
    h.expect("overweight part rejected", Reject_Pusher=True)
    h.run(500)
    h.expect("reject pulse ends after 500 ms", Reject_Pusher=False)
    h.run(500)
    h.set(Weight_Input=90); h.run(100)
    h.pulse("Photo_Eye", on=100, after=100)
    h.expect("underweight part rejected", Reject_Pusher=True)


def _band(h, sensor, steps):
    for val, outs, label in steps:
        h.set(**{sensor: val}); h.run(200)
        h.expect(label, **outs)


def t13(h):
    h.set(Setpoint=50)
    _band(h, "Temp_Sensor", [
        (40, {"Heater": True}, "heater on below setpoint - 5"),
        (50, {"Heater": True}, "heater holds inside band while heating"),
        (56, {"Heater": False}, "heater off above setpoint + 5"),
        (50, {"Heater": False}, "heater stays off inside band"),
        (44, {"Heater": True}, "heater back on below setpoint - 5")])


def t14(h):
    _band(h, "Temp_Sensor", [
        (250, {"Fan1": False, "Fan2": False}, "both fans off when cool"),
        (310, {"Fan1": True, "Fan2": False}, "fan1 on above 30.0 C"),
        (290, {"Fan1": True}, "fan1 holds between 28 and 30 C"),
        (270, {"Fan1": False}, "fan1 off below 28.0 C"),
        (360, {"Fan1": True, "Fan2": True}, "both fans on above 35.0 C"),
        (340, {"Fan2": True}, "fan2 holds between 33 and 35 C"),
        (320, {"Fan1": True, "Fan2": False}, "fan2 off below 33.0 C")])


def t15(h):
    _band(h, "Pressure_Sensor", [
        (70, {"Compressor_Motor": True}, "starts below 80 psi"),
        (100, {"Compressor_Motor": True}, "keeps running inside band"),
        (125, {"Compressor_Motor": False}, "stops above 120 psi"),
        (100, {"Compressor_Motor": False}, "stays off inside band"),
        (75, {"Compressor_Motor": True}, "restarts below 80 psi")])


def t16(h):
    for co2, pos in [(500, 0), (600, 0), (700, 25), (800, 50), (1000, 100), (1200, 100)]:
        h.set(CO2_Sensor=co2); h.run(100)
        h.expect(f"CO2 {co2} ppm -> {pos}%", tol=1, Damper_Position=pos)


def t17(h):
    h.set(Soil_Moisture=50); h.run(200)
    h.expect("valve closed when soil is moist", Irrigation_Valve=False)
    t0 = h.t
    h.pulse("Manual_Start")
    h.expect("manual start opens valve", Irrigation_Valve=True)
    h.until(t0 + 570000)
    h.expect("valve still open at 9.5 min", Irrigation_Valve=True)
    h.until(t0 + 630000)
    h.expect("valve closes after 10 min", Irrigation_Valve=False)
    h.set(Soil_Moisture=20); h.run(1000); h.set(Soil_Moisture=50); t1 = h.t
    h.until(t1 + 60000)
    h.expect("valve stays open after moisture recovers", Irrigation_Valve=True)
    h.until(t1 + 630000)
    h.expect("auto-triggered valve closes after 10 min", Irrigation_Valve=False)


def t18(h):
    h.set(Part_Good=False)
    h.hold("no reject without a detect event", 1000, Reject_Cylinder=False)
    h.set(Part_Good=True)
    h.pulse_hold("good part not rejected", "Part_Detect", 100, 900, Reject_Cylinder=False)
    h.set(Part_Good=False); h.pulse("Part_Detect", on=100, after=100)
    h.expect("failed part rejected", Reject_Cylinder=True)
    h.run(500)
    h.expect("reject pulse ends after 500 ms", Reject_Cylinder=False)


def t19(h):
    h.set(At_Floor1=True); h.run(200)
    h.pulse("Call_Floor2")
    h.hold("call to floor 2 latches up", 1000, Motor_Up=True)
    h.set(At_Floor1=False)
    h.hold("keeps moving up between floors", 500, Motor_Up=True)
    h.set(At_Floor2=True); h.run(200)
    h.expect("stops at floor 2", Motor_Up=False)
    h.pulse("Call_Floor2")
    h.expect("no up move when already at floor 2", Motor_Up=False)
    h.pulse("Call_Floor1")
    h.hold("call to floor 1 latches down", 1000, Motor_Down=True)
    h.set(At_Floor2=False)
    h.hold("keeps moving down between floors", 500, Motor_Down=True)
    h.set(At_Floor1=True); h.run(200)
    h.expect("stops at floor 1", Motor_Down=False)
    h.pulse("Call_Floor1")
    h.expect("no down move when already at floor 1", Motor_Down=False)


def t20(h):
    h.set(Part_Present=True, Gripper_Retracted=True); h.run(200)
    h.expect("idle: retracted and open", Cylinder_Extend=False, Gripper_Close=False)
    h.pulse("Start_Cycle")
    h.expect("start extends cylinder", Cylinder_Extend=True)
    h.set(Gripper_Retracted=False); h.run(300)
    h.set(Gripper_Extended=True); t0 = h.t; h.run(100)
    h.expect("gripper closes at extended position", Gripper_Close=True)
    h.expect("cylinder held extended during dwell", Cylinder_Extend=True)
    h.until(t0 + 800)
    h.expect("cylinder retracts after 500 ms dwell", Cylinder_Extend=False)
    h.set(Gripper_Extended=False); h.run(300); h.set(Gripper_Retracted=True); h.run(300)
    h.expect("gripper released when retracted", Gripper_Close=False)
    h.expect("returns to idle", Cylinder_Extend=False)


def t21(h):
    h.set(Light_Curtain_Clear=True); h.run(200)
    h.expect("fault lamp off when curtain clear", Safety_Fault_Lamp=False)
    h.pulse("Start_Button")
    h.hold("start latches conveyor", LATCH, Conveyor_Run=True)
    h.set(Light_Curtain_Clear=False); h.run(200)
    h.expect("obstruction stops conveyor", Conveyor_Run=False)
    h.expect("fault lamp on when obstructed", Safety_Fault_Lamp=True)
    h.pulse("Start_Button")
    h.expect("cannot start while obstructed", Conveyor_Run=False)
    h.set(Light_Curtain_Clear=True); h.run(300)
    h.pulse("Start_Button"); h.pulse("Stop_Button")
    h.expect("stop button stops conveyor", Conveyor_Run=False)


def t22(h):
    h.run(200)
    h.pulse("Start_Button")
    h.hold("start latches conveyor", LATCH, Conveyor_Run=True)
    h.set(Entry_Photo_Eye=True, Exit_Photo_Eye=False); t0 = h.t
    h.until(t0 + 7000)
    h.expect("no alarm before 8 s", Jam_Alarm=False)
    h.expect("conveyor runs before jam", Conveyor_Run=True)
    h.until(t0 + 9000)
    h.expect("alarm after 8 s blocked", Jam_Alarm=True)
    h.expect("jam stops conveyor", Conveyor_Run=False)
    h.set(Entry_Photo_Eye=False)
    h.hold("alarm stays latched", 1000, Jam_Alarm=True)
    h.pulse("Stop_Button")
    h.expect("stop button clears alarm", Jam_Alarm=False)
    h.pulse("Start_Button")
    h.set(Entry_Photo_Eye=True, Exit_Photo_Eye=True); h.run(10000)
    h.expect("no alarm when exit also blocked", Jam_Alarm=False)


def t23(h):
    h.run(200)
    h.pulse("Start_Button")
    h.hold("valve A open while running", LATCH, Valve_A=True)
    h.start_record("Valve_B")
    for _ in range(8):
        h.pulse("Flow_A_Pulse", on=150, after=150)
    rec = h.stop_record()
    h.check("valve B opens once per 4 flow pulses", rising_edges(rec, "Valve_B") == 2 and h.out("Valve_B") is not None,
            ["Valve_B"])
    h.pulse("Stop_Button")
    h.expect("valve A closes on stop", Valve_A=False)
    h.start_record("Valve_B")
    for _ in range(8):
        h.pulse("Flow_A_Pulse", on=150, after=150)
    rec = h.stop_record()
    h.check("no dosing while stopped", rising_edges(rec, "Valve_B") == 0 and h.out("Valve_B") is not None, ["Valve_B"])


def t24(h):
    lamps = ("Lamp1", "Lamp2", "Lamp3", "Lamp4")
    h.run(200)
    t0 = h.t
    h.start_record(*lamps)
    h.pulse("Start_Button", on=100, after=0)
    h.until(t0 + 4600)
    rec = h.stop_record()
    rec = [r for r in rec if r[0] >= t0 + 100]
    have = all(h.out(n) is not None for n in lamps)
    single = [sum(bool(v[n]) for n in lamps) == 1 for _, v in rec]
    h.check("exactly one lamp lit at a time", have and sum(single) >= 0.9 * len(single), lamps)
    segs = []
    for t, v in rec:
        on = [i + 1 for i, n in enumerate(lamps) if v[n]]
        key = on[0] if len(on) == 1 else None
        if segs and segs[-1][0] == key:
            segs[-1][2] = t
        else:
            segs.append([key, t, t])
    order = [s[0] for s in segs if s[0] is not None]
    h.check("lamps light in order 1-2-3-4, repeating", have and order[:8] == [1, 2, 3, 4, 1, 2, 3, 4], lamps)
    inner = [s for s in segs[1:-1] if s[0] is not None]
    h.check("each lamp lit for ~500 ms", have and len(inner) >= 4 and
            all(400 <= (s[2] - s[1] + SCAN) <= 600 for s in inner), lamps)
    h.pulse("Stop_Button")
    h.expect("all lamps off when stopped", **{n: False for n in lamps})
    h.pulse("Start_Button", on=100, after=100)
    h.expect("sequence restarts at Lamp1", Lamp1=True, Lamp2=False, Lamp3=False, Lamp4=False)


def t25(h):
    _band(h, "pH_Sensor", [
        (700, {"Acid_Pump": False, "Base_Pump": False}, "no dosing at pH 7.00"),
        (750, {"Acid_Pump": True, "Base_Pump": False}, "acid above 7.20"),
        (650, {"Acid_Pump": False, "Base_Pump": True}, "base below 6.80"),
        (700, {"Acid_Pump": False, "Base_Pump": False}, "dosing stops back in range")])


def t26(h):
    h.run(200)
    h.expect("idle: conveyor off", Conveyor_Run=False)
    h.pulse("Start_Button")
    h.hold("start latches conveyor", LATCH, Conveyor_Run=True)
    h.pulse("Stop_Button")
    h.expect("stop button stops conveyor", Conveyor_Run=False)


def _rpm(h, rpm, display):
    h.set(RPM_Set=rpm); h.run(200)
    h.expect("no speed output when stopped", Conveyor_Run=0)
    h.pulse("Start_Button")
    h.hold("speed output = RPM_Set while running", 1000, Conveyor_Run=rpm)
    if display:
        h.expect("display shows RPM", Digital_Display=rpm)
    h.pulse("Stop_Button")
    h.expect("speed output zero after stop", Conveyor_Run=0)


def t27(h):
    _rpm(h, 1500, display=False)


def t28(h):
    _rpm(h, 1200, display=True)


def t29(h):
    _rpm(h, 1500, display=True)


def t30(h):
    _rpm(h, 1500, display=True)


PROBES = {i: globals()[f"t{i:02d}"] for i in range(1, 31)}
