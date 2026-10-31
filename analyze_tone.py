# -*- coding: utf-8 -*-
"""单音自环分析：验证链路通、功率合适、无直流/饱和，并测频偏。

用法：
  /usr/bin/python3 analyze_tone.py [/dev/shm/rx_tone.npy]
"""
import sys
import numpy as np
import cfg

SEG = int(cfg.RATE * 0.1)   # 只分析前 0.1 秒（省内存/时间）


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else cfg.TONE_FILE
    x = np.load(path)
    print(f"[+] 文件: {path}, {len(x)} 点, {len(x)/cfg.RATE:.3f} s")

    x = x[:SEG]
    pwr = 10 * np.log10(np.mean(np.abs(x) ** 2) + 1e-12)
    print(f"[+] 功率 = {pwr:.1f} dBFS")
    if pwr > -5:
        print("[!] 功率过高，接近 ADC 满量程：降 rx_gain 或加大衰减器")
    elif pwr < -40:
        print("[!] 功率过低：升 rx_gain / tx_gain，或检查衰减器与接线")
    else:
        print("[+] 功率在合理范围 (-20 ~ -10 最好)")

    # 峰值频偏
    X = np.fft.fftshift(np.fft.fft(x * np.hanning(len(x))))
    f = np.fft.fftshift(np.fft.fftfreq(len(x), 1 / cfg.RATE))
    i = int(np.argmax(np.abs(X)))
    print(f"[+] 峰值频率 = {f[i]/1e3:.1f} kHz 相对中心频率")
    print(f"    期望 ≈ {cfg.TONE_OFFSET_HZ/1e3:.1f} kHz；偏差即收发本振差")

    # 直流检查（频偏估计的旁证：中心附近有无强峰）
    near_dc = np.abs(f) < 5e3
    dc = 10 * np.log10(np.max(np.abs(X[near_dc]) ** 2) + 1e-12)
    print(f"[+] 中心 ±5 kHz 内最高分量 = {dc:.1f} dB（明显低于峰值则无直流泄漏）")


if __name__ == "__main__":
    main()
