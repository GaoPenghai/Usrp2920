# -*- coding: utf-8 -*-
"""离线自检（不需要硬件）：模拟 TX->信道->RX，验证同步/解调/BER 逻辑。

在板子上也可以跑：/usr/bin/python3 test_sim.py
"""
import numpy as np
import cfg
import ofdm_common as oc
from analyze_ofdm import xcorr, find_sync, estimate_cfo, demod_frame

N, CP = oc.N, oc.CP


def main():
    frame, bits = oc.build_ofdm_frame()
    fl = len(frame)
    pre = oc.preamble_two()

    # 模拟连续发送：偏移 1000 处开始，连发 6 帧
    delay = 1000
    rx = np.zeros(delay + fl * 6 + 1000, np.complex64)
    for k in range(6):
        rx[delay + k * fl: delay + (k + 1) * fl] = frame

    # 频偏 + AWGN
    df = 800.0   # Hz
    n = np.arange(len(rx))
    rx = rx.astype(complex) * np.exp(1j * 2 * np.pi * df * n / cfg.RATE)
    rng = np.random.default_rng(0)
    sig_pwr = np.mean(np.abs(rx) ** 2)
    noise = rng.normal(0, 1, len(rx)) + 1j * rng.normal(0, 1, len(rx))
    noise *= np.sqrt(sig_pwr / 10 ** (15 / 10) / 2)
    rx = (rx + noise).astype(np.complex64)

    R = xcorr(rx, pre)
    p = find_sync(rx, pre)
    start = p - len(pre) + 1
    d0 = start + len(pre) + cfg.GAP_SAMPS
    cfo = estimate_cfo(rx, d0)
    print(f"真值 start={delay} 估计 start={start} 频偏真值={df}Hz 估计={cfo:.1f}Hz")

    rx2 = rx * np.exp(-1j * 2 * np.pi * cfo * n / cfg.RATE)
    b, evm_db, _ = demod_frame(rx2, start)
    nbit = min(len(b), len(bits))
    ber = np.mean(b[:nbit] != bits[:nbit])
    print(f"BER={ber:.3e} ({nbit} bit), EVM={evm_db:.1f} dB")
    assert start >= 0 and (start - delay) % fl == 0, "同步位置错误"
    assert ber < 1e-3, "解调失败"
    print("[OK] 离线自检通过")


if __name__ == "__main__":
    main()
