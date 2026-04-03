#!/usr/bin/env python3

import numpy as np
import wave
import sys


def generate_lm1_fsk(bpm, duration_sec, filename="lm1_fsk.wav",
                    leader=False, leader_freq="low",
                    f_low=1300, f_high=2100,
                    ppqn=48, sample_rate=44100):

    pulses_per_sec = (bpm / 60.0) * ppqn
    symbols_per_sec = pulses_per_sec * 2  # 2 symbols per pulse

    symbol_duration = 1.0 / symbols_per_sec
    samples_per_symbol = int(sample_rate * symbol_duration)

    total_samples = int(sample_rate * duration_sec)

    # Leader length (1 bar = 4 beats)
    leader_samples = 0
    if leader:
        seconds_per_beat = 60.0 / bpm
        leader_duration = 4 * seconds_per_beat
        leader_samples = int(sample_rate * leader_duration)

    total_length = total_samples + leader_samples
    signal = np.zeros(total_length)

    phase = 0.0
    t = 0

    # --- Leader tone ---
    if leader:
        freq = f_high if leader_freq.lower() == "hi" else f_low

        for _ in range(leader_samples):
            phase += 2 * np.pi * freq / sample_rate
            signal[t] = np.sin(phase)
            t += 1

    # --- FSK data ---
    symbol_index = 0

    while t < total_length:
        freq = f_high if (symbol_index % 2 == 0) else f_low

        for _ in range(samples_per_symbol):
            if t >= total_length:
                break

            phase += 2 * np.pi * freq / sample_rate
            signal[t] = np.sin(phase)
            t += 1

        symbol_index += 1

    # Normalize
    signal *= 0.8
    signal_int16 = np.int16(signal * 32767)

    # Write WAV
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(signal_int16.tobytes())

    print(f"Generated: {filename}")
    print(f"BPM: {bpm}, Duration: {duration_sec}s")
    if leader:
        print(f"Leader: 1 bar ({leader_freq.upper()} freq)")


# ---------------- CLI ----------------

def main():
    args = sys.argv[1:]

    if len(args) < 2:
        print("Usage:")
        print("  script.py BPM DURATION [leader] [HI/LOW] [filename]")
        print("")
        print("Examples:")
        print("  script.py 120 10")
        print("  script.py 120 10 leader hi out.wav")
        sys.exit(1)

    bpm = float(args[0])
    duration = float(args[1])

    # Defaults
    leader = False
    leader_freq = "low"
    filename = "lm1_fsk.wav"

    if len(args) >= 3:
        if args[2].lower() == "leader":
            leader = True

    if len(args) >= 4:
        leader_freq = args[3]

    if len(args) >= 5:
        filename = args[4]

    generate_lm1_fsk(
        bpm=bpm,
        duration_sec=duration,
        filename=filename,
        leader=leader,
        leader_freq=leader_freq
    )


if __name__ == "__main__":
    main()
