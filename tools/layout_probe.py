"""Post-process the plugin-generated board into the pencil-shaped moisture probe.

Run with KiCad's Python (pcbnew is only importable there):
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/layout_probe.py moisture-probe/moisture-probe.kicad_pcb

What it does (idempotent - safe to re-run after pcb_generate):
  * replaces the rectangular outline with a pencil outline (20 x 172 mm, pointed tip)
  * places every footprint in functional bands, top to bottom:
      antenna | nRF52832 + crystals + RF | test pads | sensors | piezo | boost | AAA holder | probe
  * adds an antenna copper keep-out, GND pours over the electronics section,
    and the capacitive moisture electrodes (sense plate + GND guard strips) on the probe
"""

import sys

import pcbnew as pcb

W = 20.0          # board width, mm
SHOULDER_Y = 150  # where the taper to the tip starts
TIP_Y = 172       # tip point
ANT_KEEPOUT_Y = 5.0
SOIL_LINE_Y = 128  # electronics above, electrodes below

# ref: (x, y, rotation_deg) - board origin is top-left, y grows toward the tip
PLACEMENT = {
    # RF + MCU
    "AE1": (10, 2.5, 0),
    "R1": (10, 6.2, 90), "C5": (12.2, 7.2, 0), "L4": (10, 8.6, 90),
    "U1": (10, 14.5, 0),
    "Y1": (4.9, 13.2, 0), "C1": (2.0, 11.4, 0), "C2": (2.0, 15.0, 0),
    "Y2": (15.6, 12.0, 90), "C3": (18.0, 10.6, 90), "C4": (18.0, 13.6, 90),
    "C6": (13.8, 9.8, 0), "C9": (5.0, 19.2, 0), "C7": (3.6, 17.2, 0),
    "C8": (16.6, 16.4, 90), "C15": (7.2, 21.2, 0),
    "L2": (14.0, 19.6, 0), "L3": (16.7, 19.6, 0), "C14": (10.4, 20.8, 0),
    # programming / debug pads
    "TP1": (3, 23.5, 0), "TP2": (6.5, 23.5, 0), "TP3": (10, 23.5, 0),
    "TP4": (13.5, 23.5, 0), "TP5": (17, 23.5, 0),
    # sensors (keep away from the warm boost converter)
    "U3": (4, 28.5, 0), "C10": (4, 31.2, 0),
    "U4": (10, 29.0, 0), "C11": (10, 32.6, 0),
    "U5": (16, 28.5, 0), "C12": (16, 31.2, 0),
    "R5": (6.8, 33.6, 0), "R6": (13.2, 33.6, 0),
    # buzzer
    "BZ1": (10, 42.5, 0),
    # power
    "U2": (10, 53.0, 0), "L1": (14.8, 53.5, 0),
    "C16": (5.6, 52.6, 90), "C18": (7.4, 55.8, 0), "C13": (10.2, 56.2, 0),
    "C17": (12.6, 57.2, 0),
    "D1": (3.0, 56.6, 0), "R4": (3.0, 58.4, 0),
    # battery: pads span 1.45..18.55 in x, 60.4..123.6 in y
    "BT1": (10, 92.0, 90),
    # moisture front-end, right at the soil line
    "R2": (7.5, 126.0, 90), "R3": (12.5, 126.0, 90),
}


def mm(v):
    return pcb.FromMM(v)


def pt(x, y):
    return pcb.VECTOR2I(mm(x), mm(y))


def replace_outline(board):
    edge = board.GetLayerID("Edge.Cuts")
    for d in list(board.GetDrawings()):
        if d.GetLayer() == edge:
            board.Remove(d)
    pts = [(0, 0), (W, 0), (W, SHOULDER_Y), (W / 2, TIP_Y), (0, SHOULDER_Y)]
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s = pcb.PCB_SHAPE(board)
        s.SetShape(pcb.SHAPE_T_SEGMENT)
        s.SetLayer(edge)
        s.SetWidth(mm(0.1))
        s.SetStart(pt(x1, y1))
        s.SetEnd(pt(x2, y2))
        board.Add(s)


def place(board):
    missing = []
    # FindFootprintByReference returns an unwrapped SwigPyObject on KiCad 10
    by_ref = {f.GetReference(): f for f in board.GetFootprints()}
    for ref, (x, y, rot) in PLACEMENT.items():
        fp = by_ref.get(ref)
        if fp is None:
            missing.append(ref)
            continue
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
    unplaced = [f.GetReference() for f in board.GetFootprints() if f.GetReference() not in PLACEMENT]
    return missing, unplaced


def _zone(board, layers, poly, net=None, name="", priority=0, clearance=0.3):
    z = pcb.ZONE(board)
    ls = pcb.LSET()
    for l in layers:
        ls.AddLayer(board.GetLayerID(l))
    z.SetLayerSet(ls)
    chain = z.Outline()
    chain.NewOutline()
    for x, y in poly:
        chain.Append(mm(x), mm(y))
    if net is not None:
        z.SetNet(board.FindNet(net))
    z.SetZoneName(name)
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(clearance))
    z.SetMinThickness(mm(0.2))
    board.Add(z)
    return z


def add_zones(board):
    # drop zones from a previous run
    for z in list(board.Zones()):
        board.Remove(z)

    # antenna keep-out: no copper pour or tracks under/around the chip antenna
    ko = _zone(board, ["F.Cu", "B.Cu"], [(0, 0), (W, 0), (W, ANT_KEEPOUT_Y), (0, ANT_KEEPOUT_Y)], name="ANT_KEEPOUT")
    ko.SetIsRuleArea(True)
    for setter in ("SetDoNotAllowZoneFills", "SetDoNotAllowCopperPour"):
        if hasattr(ko, setter):
            getattr(ko, setter)(True)
            break
    ko.SetDoNotAllowTracks(True)
    ko.SetDoNotAllowVias(True)
    ko.SetDoNotAllowFootprints(False)
    if hasattr(ko, "SetDoNotAllowPads"):
        ko.SetDoNotAllowPads(False)  # the antenna's own pads live here

    # GND pour over the electronics section (both layers). Solid pad
    # connections: 0.4 mm-pitch QFN/DSBGA GND pads can't fit 2 thermal spokes.
    # Islands are removed here only - the electrode zones below are
    # deliberately "isolated" until routed and must not be deleted.
    gnd_poly = [(0, ANT_KEEPOUT_Y), (W, ANT_KEEPOUT_Y), (W, SOIL_LINE_Y), (0, SOIL_LINE_Y)]
    for layer, name in (("F.Cu", "GND_TOP"), ("B.Cu", "GND_BOT")):
        z = _zone(board, [layer], gnd_poly, net="GND", name=name)
        z.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcb.ISLAND_REMOVAL_MODE_ALWAYS)

    # moisture electrodes: centre sense plate flanked by GND guard strips,
    # same pattern on both layers so the field reaches soil on both faces.
    # Left under solder mask (zones are masked by default) - do NOT expose copper to soil.
    sense = [(7, 129.5), (13, 129.5), (13, 152), (10, 160), (7, 152)]
    guard_l = [(0.8, 129.5), (4.2, 129.5), (4.2, 149), (0.8, 149)]
    guard_r = [(15.8, 129.5), (19.2, 129.5), (19.2, 149), (15.8, 149)]
    for layer in ("F.Cu", "B.Cu"):
        _zone(board, [layer], sense, net="MOIST_SNS", name=f"ELECTRODE_{layer[0]}", priority=1, clearance=0.5)
        _zone(board, [layer], guard_l, net="GND", name=f"GUARD_L_{layer[0]}", priority=1, clearance=0.5)
        _zone(board, [layer], guard_r, net="GND", name=f"GUARD_R_{layer[0]}", priority=1, clearance=0.5)


def main(path):
    board = pcb.LoadBoard(path)
    # Order matters on KiCad 10's SWIG bindings: removing/adding drawings first
    # leaves GetFootprints() pointing at freed memory (access violation).
    missing, unplaced = place(board)
    add_zones(board)
    replace_outline(board)
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    print(f"saved {path}")
    if missing:
        print("not on board (check refs):", ", ".join(missing))
    if unplaced:
        print("footprints without a placement entry:", ", ".join(unplaced))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "moisture-probe/moisture-probe.kicad_pcb")
