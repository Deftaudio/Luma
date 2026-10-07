# Luma 8-bit DAC firmware, clocked revision (Deftaudio)

Standalone firmware for the **PicoROM Original (POG)** hardware that turns it into a USB audio interface for the **Luma-mu** (Am6070 μ-law DAC). Plug the PicoROM into Luma-mu's EPROM socket.
Only the board and its pin map are reused. There is no PicoROM code in it.

This revision lets Luma-mu itself clock the output. Its sample clock (pitch knob, pitch CV or external clock jack) sets the output sample rate, and its **voice select** chooses one of eight modes. 

- **USB device:** manufacturer "Deftaudio", product "Luma 8-bit DAC". It is a USB Audio Class 2 device, stereo, 16-bit PCM, at 44.1 kHz or 48 kHz. It needs no driver on macOS, Windows 10+ or Linux.
- **Left channel:** encoded to **8-bit μ-law in Am6070 format** and written to the ROM data pins D0..D7. This is the same byte format as Luma-1 / Luma-mu sample ROMs: G.711 μ-law without the final bit inversion. Bit 7 = sign, bits 6–4 = chord, bits 3–0 = step. `0x00` = silence, `0x7F` = positive full scale, `0xFF` = negative full scale.
- **Right channel:** accepted and discarded.
- **USB clocking:** adaptive isochronous mode, with no feedback endpoint. Samples are taken from USB at exactly the host rate by a "pacer" PIO state machine. Its clock divider is nudged after every USB packet (1/256 steps, about 5 ppm) to keep the buffer level constant. The tracking range is ±1000 ppm.
- **Output clocking:** set by the voice select, see below.
- **Volume and mute:** the host controls are applied in the linear domain before μ-law encoding, from −50 dB to 0 dB in 1 dB steps.
- **Latency:** about 4 ms of buffering.
- **Robustness:**
  - The firmware works around a TinyUSB 0.18 / RP2040 bug that panicked the chip when a stream was restarted. It disarms the isochronous endpoint whenever streaming stops.
  - A 500 ms watchdog reboots the chip if it ever locks up. The board is powered from the socket, so unplugging USB alone does not reset it.

## Output pins

The data lines reach the socket through the board's 74LVCH8T245 level shifter. On rev 1.7 the shifter's /OE is tied to GND, and the net labelled `BUF_OE` (GPIO19) actually drives its **DIR** pin. The firmware holds DIR low, so the Pico always drives the socket.

| Signal                   | RP2040 | DIP-32 socket pin |
| ------------------------ | ------ | ----------------- |
| D0 (LSB)                 | GPIO22 | 13                |
| D1                       | GPIO23 | 14                |
| D2                       | GPIO24 | 15                |
| D3                       | GPIO25 | 17                |
| D4                       | GPIO26 | 18                |
| D5                       | GPIO27 | 19                |
| D6                       | GPIO28 | 20                |
| D7 (MSB)                 | GPIO29 | 21                |
| GND                      | —      | 16                |
| VCC (5 V)                | —      | 32                |
| Shifter DIR (driven low) | GPIO19 | —                 |
| TCA5405 expander (LEDs)  | GPIO18 | —                 |

**Power:** the shifter's socket-side rail comes from USB VBUS or socket pin 32, through Schottky diodes. Logic high is that rail minus about 0.3 V, so use the same rail as the R-2R reference.

- **Green LED (D2):** on while the host is streaming and audio is flowing.
- **Red LED (D1):** power, wired directly to 3.3 V.
- **Amber LED (D3):** on while a Luma-mu sample clock is detected on A0.

D2 and D3 are driven through the TCA5405 single-wire expander on GPIO18, using the same bit framing and timing as the PicoROM firmware. The expander's reset output stays disabled (Hi-Z).

## Luma-mu wiring

The PicoROM data pins go straight into Luma-mu's Am6070. There is no latch in between:

| EPROM data | Am6070 input | μ-law field      |
| ---------- | ------------ | ---------------- |
| D7         | SB           | sign             |
| D6, D5, D4 | B1, B2, B3   | chord (B1 = MSB) |
| D3..D0     | B4..B7       | step (B7 = LSB)  |

Luma-mu still has to be in the **playing** state: INHIBIT drives the Am6070 E/D pin and steers its output current away when the module is idle. Loop mode (JP2 removed, then trigger once) keeps it playing. The DYNAMIC control sets the Am6070 reference, and so still acts as the output level.

## How Luma-mu clocks the output

- `SAMPLE_CLK = COUNTER_CLK AND NOT /PAUSE` (U7A, U9A). `COUNTER_CLK` is the 555 (pitch knob and pitch CV) or the external clock jack.
- `SAMPLE_CLK` drives a 74LS393 ripple counter that advances on each falling edge.
- **A0 toggles once per sample period**, so every A0 edge (rising and falling) is one Luma-mu sample. A1 toggles at half that rate.

Address lines reach the Pico through 74LVCH245 buffers that are always enabled (socket → RP2040):

| Signal                    | RP2040     | Use                                                 |
| ------------------------- | ---------- | --------------------------------------------------- |
| A0                        | GPIO0      | output sample clock (both edges)                    |
| A1                        | GPIO1      | output sample clock ÷ 2 (both edges)                |
| A0..A13                   | GPIO0..13  | 16 KB address for the Live ROM and Sampler voices   |
| A14, A15, A16 = BANK_0..2 | GPIO14..16 | voice select 0..7 (the number on Luma-mu's display) |

A live stream cannot be played faster or slower without running out of data or overflowing. So a lower Luma-mu rate works as a **sample-and-hold rate reducer**: on each clock edge the newest sample is latched onto D0..D7 and held until the next edge. Pitch and timing stay correct, and aliasing grows as the rate drops (the classic vintage-sampler crunch). A PIO state machine does the latching about 30 ns after the edge.

When Luma-mu's clock stops, the module is not playing and INHIBIT mutes the Am6070. So the clocked voices simply hold the last sample; there is no fallback clock.

## Voice select

The voice is read from A14..A16, which is Luma-mu's BANK_0..2 (the digit on its display). It is debounced for 10 ms, so sweeping the knob past a position does not trigger it.

| Voice | Output clock                           | Effect                                          |
| ----- | -------------------------------------- | ----------------------------------------------- |
| 0     | host rate (44.1/48 kHz), no reclocking | none; the pitch control has no effect           |
| 1     | every A0 edge                          | raw sample-and-hold (aliasing)                  |
| 2     | every A0 edge                          | raw + **resonant low-pass** following the clock |
| 3     | every A1 edge (½ rate)                 | raw                                             |
| 4     | every A1 edge (½ rate)                 | raw + **resonant low-pass** following the clock |
| 5     | Luma-mu address                        | **Live ROM:** pitch shifter                     |
| 6     | Luma-mu address                        | **Sampler:** snapshot of the last 0.34 s        |
| 7     | host rate, no reclocking               | μ-law bit crush, depth set by the Luma-mu clock |

- **Resonant low-pass (2, 4):**
  
  - It is a trapezoidal state-variable filter, Q = 8, stable up to Nyquist, computed at the USB rate before the sample-and-hold.
  - Its cutoff is 0.3 × the output sample rate (the Luma-mu rate, or half of it on voice 4), from A0 edge timestamps updated every 10 ms. Sweeping the pitch knob or CV sweeps the resonant peak with it.
  - Response: the passband is 6 dB down to leave headroom, the peak at the cutoff is about +18 dB above the passband, and it falls about 18 dB per octave above the cutoff. Loud material clips at the resonance, which is part of the effect.
  - Tune `RESO_Q` and `RESO_FC_RATIO` in `main.c`.

- **Live ROM (5):**
  
  - The PicoROM behaves as an EPROM again. Its 16 K-sample "ROM" is a ring buffer continuously written with the live stream at the USB rate.
  - Luma-mu's address counter reads it at its own rate, so the **pitch knob really shifts pitch**.
  - The audio is about 0.34 s behind, with a periodic jump where the read and write positions cross (a granular / tape pitch-shifter character).
  - Triggering restarts the read position. The buffer is cleared when the host stops streaming.

- **Sampler (6):**
  
  - Selecting voice 6 freezes the last 16 K samples (about 0.34 s at 48 kHz), with address 0 = the oldest sample.
  - Luma-mu then plays it exactly as it would play an EPROM sample: trigger, one-shot or loop, pitch, pause.
  - Select another voice and come back to take a new snapshot. The snapshot survives the stream stopping.

- **Bit crush (7):**
  
  - The output stays at the host rate. The Luma-mu clock (pitch knob, CV or clock jack) sets how many bits of each μ-law code are kept, log-spaced from 28 kHz (8 bits) to 5 kHz (1 bit). The kept bits are the top ones: sign, then chord, then step.
    
    | Luma-mu clock | ≥ 28 kHz  | ~21.9 kHz | ~17.1 kHz | ~13.4 kHz | ~10.5 kHz        | ~8.2 kHz | ~6.4 kHz | ≤ 5 kHz                    |
    | ------------- | --------- | --------- | --------- | --------- | ---------------- | -------- | -------- | -------------------------- |
    | Bits          | 8 (clean) | 7         | 6         | 5         | 4 (sign + chord) | 3        | 2        | 1 (sign only: square wave) |
  
  - The dropped bits are set to the middle of their range, and exact silence stays silent.
  
  - There is a 0.15-bit hysteresis, so it does not flicker at a boundary.
  
  - Tune `CRUSH_RATE_8BIT` and `CRUSH_RATE_1BIT` in `main.c`.

In the Live ROM and Sampler voices, core 1 watches the address bus and presents `rom[address]` within about 0.5 µs of an address change. It waits for two identical reads, so the ripple counter has settled. Luma-mu's 16 KB counter wraps in loop mode, and in one-shot mode it stops at 16 K and raises INHIBIT, as with a real EPROM.

## Flashing

1. Enter BOOTSEL mode: bridge the `USB` and `GND` pads on the header near the RP2040 while powering on (see PicoROM's INSTALL.md). A board still running PicoROM firmware can also be sent to BOOTSEL with `picorom firmware`.
2. Copy one `.uf2` file onto the `RPI-RP2` drive.

Once this firmware is installed, you need the pad bridge for every later update.

## 

- `main.c`: USB audio, rate tracking, voice modes and effects (core 0), and the output engine (core 1).
- `board.h`: POG pin map, including the address bus.
- `dac_out.pio`: the pacer, latch, follow and TCA5405 state machines.
- `usb_descriptors.c/.h`, `tusb_config.h`: the UAC2 adaptive speaker descriptor.
