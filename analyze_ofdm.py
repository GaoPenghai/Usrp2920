# -*- coding: utf-8 -*-
"""OFDM 自环分析：帧同步 -> 频偏补偿 -> FFT -> 导频信道估计 -> 均衡 -> QPSK 判决 -> BER/EVM。

用法：
  /usr/bin/python3 analyze_ofdm.py [/dev/shm/rx_capture.npy]

前提：先跑过 loopback.py --wave ofdm，它会把已知比特存到 cfg.TX_META。
"""
import sys
import numpy as np

import cfg
import ofdm_common as oc

N, CP = oc.N, oc.CP
SEG_SEC = 0.1          # 只分析前 0.1 秒（帧率 ~470/s，足够 40+ 帧）
MAX_FRAMES = 20        # 统计前 20 帧


def xcorr(sig, tmpl):
    """互相关；峰位置 p 对应 tmpl 起点在 sig 中的 start = p - len(tmpl) + 1"""
    b = np.conj(tmpl[::-1]).astype(np.complex64)
    n = len(sig) + len(b) - 1
    nfft = 1 << (n - 1).bit_length()
    return np.fft.ifft(np.fft.fft(sig, nfft) * np.fft.fft(b, nfft))


def find_sync(seg, pre):
    """返回最强相关峰位置 p（峰位于 p 时 tmpl 起点 start = p-len(pre)+1）。
    帧连续重复时，该峰落在任意一帧的起点，后续按 frame_len 推进即可。"""
    absR = np.abs(xcorr(seg, pre))
    p = int(np.argmax(absR))
    lo, hi = max(0, p - 64), min(len(absR), p + 65)
    return lo + int(np.argmax(absR[lo:hi]))


def estimate_cfo(seg, d0):
    """用第一个数据符号的 CP 相关估计频偏（Hz）"""
    c = np.sum(np.conj(seg[d0:d0 + CP]) * seg[d0 + N:d0 + N + CP])
    return np.angle(c) * cfg.RATE / (2.0 * np.pi * N)


def demod_symbol(Y):
    """Y: FFT 后频域样点 -> (判决比特, 均衡后数据符号)"""
    Hp = Y[oc.PILOT_IDX]                     # 导频值=1，LS 即 H
    Hre = np.interp(oc.DATA_IDX, oc.PILOT_IDX, Hp.real)
    Him = np.interp(oc.DATA_IDX, oc.PILOT_IDX, Hp.imag)
    Yd = Y[oc.DATA_IDX] / (Hre + 1j * Him)
    bits = np.empty(len(oc.DATA_IDX) * 2, dtype=np.uint8)
    bits[0::2] = (Yd.real < 0)
    bits[1::2] = (Yd.imag < 0)
    return bits, Yd


def demod_frame(seg, start):
    """解调一帧：返回 (bits, evm_db, 均衡符号)"""
    d0 = start + len(oc.preamble_two()) + cfg.GAP_SAMPS
    bits_all = []
    syms = []
    for i in range(cfg.N_DATA_SYM):
        off = d0 + i * (N + CP)
        Y = np.fft.fft(seg[off + CP:off + CP + N])
        b, Yd = demod_symbol(Y)
        bits_all.append(b)
        syms.append(Yd)
    bits = np.concatenate(bits_all)
    syms = np.concatenate(syms)
    ideal = ((1 - 2.0 * (syms.real < 0)) + 1j * (1 - 2.0 * (syms.imag < 0))) / np.sqrt(2.0)
    err = syms - ideal
    evm = np.sqrt(np.mean(np.abs(err) ** 2) / np.mean(np.abs(ideal) ** 2))
    return bits, 20 * np.log10(evm + 1e-12), syms


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else cfg.RX_FILE
    x = np.load(path)
    meta = np.load(cfg.TX_META)
    tx_bits = meta["bits"]

    seg = x[:int(cfg.RATE * SEG_SEC)]
    pre = oc.preamble_two()
    p = find_sync(seg, pre)
    start = p - len(pre) + 1
    print(f"[+] 同步峰位置 {p}，帧起点 {start}")
    if start < 0:
        print("[!] 没找到前导：检查 OFDM 是否是 TX 实际发送的波形、功率是否合适")
        return

    d0 = start + len(pre) + cfg.GAP_SAMPS
    cfo = estimate_cfo(seg, d0)
    print(f"[+] 频偏估计 {cfo:.1f} Hz（相对 {N} 点 CP 的相位旋转）")

    n = np.arange(len(seg))
    seg = seg * np.exp(-1j * 2 * np.pi * cfo * n / cfg.RATE)

    fl = oc.frame_len()
    n_fr = min(MAX_FRAMES, max(1, len(seg) // fl))
    print(f"[+] 帧长 {fl} 样点，统计 {n_fr} 帧")

    ber_tot = 0
    bit_tot = 0
    evm_list = []
    for f in range(n_fr):
        st = start + f * fl
        if st + fl > len(seg):
            break
        b, evm_db, _ = demod_frame(seg, st)
        nbit = min(len(b), len(tx_bits))
        ber_tot += int(np.sum(b[:nbit] != tx_bits[:nbit]))
        bit_tot += nbit
        evm_list.append(evm_db)

    if bit_tot == 0:
        print("[!] 没有有效帧")
        return
    ber = ber_tot / bit_tot
    print(f"[+] BER = {ber:.3e}  ({ber_tot}/{bit_tot} bit)")
    print(f"[+] EVM = {np.mean(evm_list):.2f} dB (均值，越低越好)")
    print(f"[+] 每帧 EVM 前几帧: {[f'{e:.1f}' for e in evm_list[:5]]}")

    if ber < 1e-2:
        print("[+] 通过：BER <= 1e-2（任务书建议指标）")
    elif ber < 0.1:
        print("[~] 可收敛但偏大：看 EVM、overflow、功率与频偏")
    else:
        print("[!] BER 过大：优先查 功率是否饱和/过低、帧同步峰是否唯一")


if __name__ == "__main__":
    main()
