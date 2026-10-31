# -*- coding: utf-8 -*-
"""深挖：解调一帧，看导频幅度、H 相位、星座分布，并扫描 start 偏移找最佳 BER。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cfg
import ofdm_common as oc

N, CP = oc.N, oc.CP
x = np.load(r"D:\Xiangmu\usrp_loopback\debug\rx_capture.npy")
meta = np.load(r"D:\Xiangmu\usrp_loopback\debug\tx_meta.npz")
tx_bits = meta["bits"]
pre = oc.preamble_two()

frame_len = oc.frame_len()
# 已知帧起点：8107 + k*frame_len（从终端输出核对）
start0 = 8107 + 43 * frame_len


def demod(start):
    d0 = start + len(pre) + cfg.GAP_SAMPS
    if d0 + cfg.N_DATA_SYM * (N + CP) > len(x):
        return None
    bits_all, syms_all = [], []
    Hs = []
    for i in range(cfg.N_DATA_SYM):
        off = d0 + i * (N + CP)
        Y = np.fft.fft(x[off + CP:off + CP + N])
        Hp = Y[oc.PILOT_IDX]
        Hs.append(Hp)
        Hre = np.interp(oc.DATA_IDX, oc.PILOT_IDX, Hp.real)
        Him = np.interp(oc.DATA_IDX, oc.PILOT_IDX, Hp.imag)
        Yd = Y[oc.DATA_IDX] / (Hre + 1j * Him)
        bits = np.empty(len(oc.DATA_IDX) * 2, np.uint8)
        bits[0::2] = (Yd.real < 0)
        bits[1::2] = (Yd.imag < 0)
        bits_all.append(bits)
        syms_all.append(Yd)
    bits = np.concatenate(bits_all)
    syms = np.concatenate(syms_all)
    return bits, syms, Hs


# 1) 导频幅度与相位（第一个数据符号）
b, syms, Hs = demod(start0)
Hp = Hs[0]
print(f"导频 |H|: mean={np.mean(np.abs(Hp)):.1f} std={np.std(np.abs(Hp)):.1f}")
print(f"导频相位散布: {np.rad2deg(np.std(np.angle(Hp))):.1f} deg")
print(f"数据符号 |Yd|: mean={np.mean(np.abs(syms)):.3f} pos_std={np.std(syms.real):.3f}")

# 星座象限统计（正常 QPSK 应各象限约 25%）
q = ((syms.real > 0).astype(int) + 2 * (syms.imag > 0).astype(int))
print("象限分布:", {k: int(np.sum(q == k)) for k in range(4)})

# 2) 第一个符号的星座（抽 12 个点）
print("前 12 个均衡符号:", np.round(syms[:12], 2))

# 3) 扫描 start 偏移
print("\nstart 偏移扫描（BER）:")
fl = frame_len
for d in range(-1200, 1201, 200):
    st = start0 + d
    r = demod(st)
    if r is None:
        continue
    b2 = r[0]
    nbit = min(len(b2), len(tx_bits))
    ber = np.mean(b2[:nbit] != tx_bits[:nbit])
    print(f"  d={d:+5d}  BER={ber:.3f}")
