"""Behaviour category of every ACTIVE probe check (one that a program which
never drives an output fails), assigned by hand.

  memory  - a past event must persist: seal-in after a momentary press,
            a running cycle, latched faults/alarms, hysteresis in a dead band
  timing  - delays, pulses, step sequences and counting
  direct  - the response to the current inputs, including numeric values
"""

MEMORY = {
    1: ["start latches pump"],
    3: ["start latches motor", "fault stays latched", "restart after reset"],
    4: ["valve opens: bottle present, not full", "valve reopens for next bottle"],
    6: ["start latches motor", "fault stays latched", "restart after reset"],
    8: ["start opens both valves"],
    9: ["open button latches opening", "close button latches closing"],
    13: ["heater holds inside band while heating"],
    14: ["fan1 holds between 28 and 30 C", "fan2 holds between 33 and 35 C"],
    15: ["keeps running inside band"],
    19: ["call to floor 2 latches up", "keeps moving up between floors",
         "call to floor 1 latches down", "keeps moving down between floors"],
    21: ["start latches conveyor"],
    22: ["start latches conveyor", "conveyor runs before jam", "alarm stays latched"],
    23: ["valve A open while running"],
    26: ["start latches conveyor"],
}
TIMING = {
    2: ["red phase", "green phase", "yellow phase", "cycle repeats (red)", "cycle repeats (green)"],
    4: ["count = 1 after first bottle", "count = 2 after second bottle"],
    5: ["alarm after 10 s at high level"],
    8: ["mixer still running before 30 s", "batch complete after mixing"],
    10: ["wash runs first", "wash still on at 19 s", "rinse follows 20 s wash", "rinse still on at 34 s",
         "dryer follows 15 s rinse", "cycle complete after 10 s drying"],
    11: ["display counts boxes", "pusher fires on 5th box", "counting restarts from zero"],
    12: ["overweight part rejected", "underweight part rejected"],
    17: ["manual start opens valve", "valve still open at 9.5 min", "valve stays open after moisture recovers"],
    18: ["failed part rejected"],
    20: ["start extends cylinder", "gripper closes at extended position", "cylinder held extended during dwell"],
    22: ["alarm after 8 s blocked"],
    23: ["valve B opens once per 4 flow pulses"],
    24: ["exactly one lamp lit at a time", "lamps light in order 1-2-3-4, repeating", "each lamp lit for ~500 ms",
         "sequence restarts at Lamp1"],
}


def category(task, label):
    if label in MEMORY.get(task, []):
        return "memory"
    if label in TIMING.get(task, []):
        return "timing"
    return "direct"
