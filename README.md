# Smart Moisture Sensor

A pencil-shaped, battery-powered Bluetooth Low Energy soil probe. You push the pointed end into the soil. Electrodes on that end measure soil moisture capacitively. The part that stays above ground measures air temperature, humidity, pressure and light, and reports the readings over BLE.

The hardware is designed in **KiCad 10**, with parts chosen for **JLCPCB** assembly.

> **Status:** schematic done. Footprints are placed and the zones are defined, but the board is **not routed yet**. There is no firmware in this repo yet.

## Board at a glance

- **Outline:** 20 × 172 mm, 2 layers. The board narrows to a point starting at y = 150 mm.
- **Layout, from the top of the board to the tip:**

  ```
  ┌──────────┐  0 mm
  │ antenna  │  chip antenna + copper keep-out (0–5 mm)
  │ nRF52832 │  MCU, 32 MHz / 32.768 kHz crystals, RF match, DC/DC filter
  │ ○○○○○    │  test pads: SWDIO, SWDCLK, RESET, 3V3, GND
  │ sensors  │  SHT40 · MS5607 · OPT3004
  │ buzzer   │  piezo
  │ power    │  TPS610994 boost, status LED
  │          │
  │ AAA cell │  battery holder
  │          │
  ├──────────┤  128 mm: soil line
  │ ▌ █ ▐    │  electrodes: sense plate between GND guard strips
  │  \  /    │
  └───\/─────┘  172 mm: tip
  ```

## Main components

| Ref | Part | Function | LCSC |
|-----|------|----------|------|
| U1 | nRF52832-QFAA | BLE SoC (Cortex-M4F) | C77540 |
| U2 | TPS610994YFFR | Boost converter, 0.7–5.5 V in → 3.3 V | C2650335 |
| U3 | SHT40-AD1B | Temperature and humidity (I²C) | C2909890 |
| U4 | MS560702BA03 | Barometric pressure (I²C) | C97627 |
| U5 | OPT3004DNPR | Ambient light (I²C, interrupt on `LIGHT_INT`) | C2655153 |
| AE1 | 2450AT42A100E | 2.4 GHz chip antenna | C2917719 |
| Y1 | X201632MKB4SI | 32 MHz crystal | C718072 |
| Y2 | Q13FC13500004 | 32.768 kHz crystal | C32346 |
| BZ1 | PKLCS1212E4001 | 4 kHz piezo buzzer, driven differentially | C113159 |
| L1 | APH0420T1R0M | 1 µH boost inductor | C5349664 |
| BT1 | BH-AAA-B5AA001 | AAA battery holder | C964881 |
| D1 | Green LED | Status LED | n/a |

The board runs from a single AAA cell. U2 boosts the cell voltage to 3V3 for everything else. The nRF52832's internal DC/DC regulator is used (L2 and L3 on `DCC`/`DEC4`).

### Moisture measurement

The sense plate (`MOIST_SNS`) and the GND guard strips on each side form a capacitor. Soil moisture changes its capacitance. The same electrode pattern is on both copper layers, so the probe senses soil on both faces.

- `MOIST_DRV` (GPIO) charges the plate through R2 (1 MΩ).
- `MOIST_AIN` (SAADC input) reads the plate voltage through R3 (1 kΩ).

The charge time (RC) indicates the moisture level. The electrodes stay **under solder mask**, so no bare copper touches the soil.

## Repository layout

```
moisture-probe/            KiCad project
  moisture-probe.kicad_sch   schematic
  moisture-probe.kicad_pcb   PCB
  libs/                      JLCPCB/LCSC symbols (C*.kicad_sym) and footprints (kicad_jlcpcb.pretty)
tools/
  layout_probe.py          pcbnew script: board outline, placement, zones
```

## Regenerating the layout

[tools/layout_probe.py](tools/layout_probe.py) takes the board produced by the JLCPCB plugin and turns it into the probe. The script:

- replaces the outline with the pencil shape
- places every footprint at fixed coordinates
- adds the antenna keep-out, the GND pours and the electrode zones
- fills the zones

You can run it more than once safely. It has to run with KiCad's bundled Python, because `pcbnew` is only importable there:

```sh
"C:/Program Files/KiCad/10.0/bin/python.exe" tools/layout_probe.py moisture-probe/moisture-probe.kicad_pcb
```

Close the board in KiCad before you run it, then reopen it afterwards. To move a part, edit the `PLACEMENT` table at the top of the script.

## Next steps

- [ ] Route the board and pass DRC
- [ ] Generate the BOM and CPL files for JLCPCB assembly
- [ ] Write the firmware: BLE advertising, sensor drivers, moisture calibration
- [ ] Design an enclosure or conformal coating for the electronics above the soil line
