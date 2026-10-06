# Luma 8-bit DAC firmware (Deftaudio)

Standalone firmware for the **PicoROM Original (POG)** hardware that turns it into a USB audio interface for the **Luma-mu** (Am6070 μ-law DAC). Plug the PicoROM into Luma-mu's EPROM socket.
Only the board and its pin map are reused. There is no PicoROM code in it.

- **USB device:** manufacturer "Deftaudio", product "Luma 8-bit DAC". It is a USB Audio Class 2 device, stereo, 16-bit PCM, at 44.1 kHz or 48 kHz. It needs no driver on macOS, Windows 10+ or Linux.
- **Left channel:** encoded to **8-bit μ-law in Am6070 format** and written to the ROM data pins D0..D7. This is the same byte format as Luma-1 / Luma-mu sample ROMs: G.711 μ-law without the final bit inversion. Bit 7 = sign, bits 6–4 = chord, bits 3–0 = step. `0x00` = silence, `0x7F` = positive full scale, `0xFF` = negative full scale.
- **Right channel:** accepted and discarded.
- **Clocking:** adaptive isochronous mode, with no feedback endpoint. The DAC follows the host's clock. After every USB packet the firmware measures how much audio is buffered and nudges the PIO clock divider (1/256 steps, about 1.3 ppm) to keep that level constant. The system clock is 144 MHz, which gives a nominal divider of 3000 at 48 kHz, and the tracking range is ±1000 ppm. No OS-specific workarounds are needed.
- **Volume and mute:** the host controls are applied in the linear domain before μ-law encoding, from −50 dB to 0 dB in 1 dB steps.
- **Latency:** about 4 ms of buffering.
- **Robustness:**
  - The firmware works around a TinyUSB 0.18 / RP2040 bug that panicked the chip when a stream was restarted. It disarms the isochronous endpoint whenever streaming stops.
  - A 500 ms watchdog reboots the chip if it ever locks up. The board is powered from the socket, so unplugging USB alone does not reset it.

## Firmware images

| File | Description |
|---|---|
| `bin/luma_dac_pog.uf2` | Plain μ-law encoding |
| `bin/luma_dac_pog_dither.uf2` | TPDF dither added before μ-law quantization, scaled to the step size of the current chord. It removes low-level quantization distortion and adds a little noise that follows the signal level. |

## Output pins

The data lines reach the socket through the board's 74LVCH8T245 level shifter. On rev 1.7 the shifter's /OE is tied to GND, and the net labelled `BUF_OE` (GPIO19) actually drives its **DIR** pin. The firmware holds DIR low, so the Pico always drives the socket.

| Signal | RP2040 | DIP-32 socket pin |
|---|---|---|
| D0 (LSB) | GPIO22 | 13 |
| D1 | GPIO23 | 14 |
| D2 | GPIO24 | 15 |
| D3 | GPIO25 | 17 |
| D4 | GPIO26 | 18 |
| D5 | GPIO27 | 19 |
| D6 | GPIO28 | 20 |
| D7 (MSB) | GPIO29 | 21 |
| GND | — | 16 |
| VCC (5 V) | — | 32 |
| Shifter DIR (driven low) | GPIO19 | — |
| TCA5405 expander (LEDs) | GPIO18 | — |

**Power:** the shifter's socket-side rail comes from USB VBUS or socket pin 32, through Schottky diodes. Logic high is that rail minus about 0.3 V, so use the same rail as the R-2R reference.

- **Green LED (D2):** on while the host is streaming and audio is flowing.
- **Red LED (D1):** power, wired directly to 3.3 V.
- **Amber LED (D3):** unused.

D2 and D3 are driven through the TCA5405 single-wire expander on GPIO18, using the same bit framing and timing as the PicoROM firmware. The expander's reset output stays disabled (Hi-Z).

## Luma-mu wiring

The PicoROM data pins go straight into Luma-mu's Am6070. There is no latch in between:

| EPROM data | Am6070 input | μ-law field |
|---|---|---|
| D7 | SB | sign |
| D6, D5, D4 | B1, B2, B3 | chord (B1 = MSB) |
| D3..D0 | B4..B7 | step (B7 = LSB) |

The DAC follows the data lines continuously, so the output sample rate is the USB rate (44.1/48 kHz) set by this firmware. Luma-mu's address counter, the 555 pitch clock and the bank select have no effect, because the PicoROM ignores the address lines. Luma-mu still has to be in the **playing** state: INHIBIT drives the Am6070 E/D pin and steers its output current away when the module is idle. Loop mode (JP2 removed, then trigger once) keeps it playing. The DYNAMIC control sets the Am6070 reference, and so still acts as the output level.

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
```

```bash
make -C build -j8
```

This produces `build/luma_dac_pog.uf2` and `build/luma_dac_pog_dither.uf2`. The SDK path defaults to `/Users/andrei/Documents/pico-sdk`, and the `PICO_SDK_PATH` environment variable overrides it.

## Flashing

1. Enter BOOTSEL mode: bridge the `USB` and `GND` pads on the header near the RP2040 while powering on (see PicoROM's INSTALL.md). A board still running PicoROM firmware can also be sent to BOOTSEL with `picorom firmware`.
2. Copy one `.uf2` file onto the `RPI-RP2` drive.

Once this firmware is installed, you need the pad bridge for every later update.

USB VID/PID: the firmware uses TinyUSB's test VID `0xCafe`. Change it in `usb_descriptors.c` before distributing.

## Files

- `main.c`: clocks, pins, USB audio callbacks, sample conversion. Core 1 feeds the PIO.
- `board.h`: POG pin map.
- `dac_out.pio`: a one-instruction state machine (`out pins, 8`) paced by its clock divider.
- `usb_descriptors.c/.h`, `tusb_config.h`: the UAC2 adaptive speaker descriptor.
