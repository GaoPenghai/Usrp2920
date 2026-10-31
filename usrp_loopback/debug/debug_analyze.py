# -*- coding: utf-8 -*-
"""离线诊断：把抓到的 IQ 逐项拆开，判断 BER=0.5 的根因。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cfg
import ofdm_common as oc

N, CP = oc.N, oc.CP
x = np.load(r"D:\Xiangmu\usrp_loopback\debug\rx_capture.npy")
print(f"len={len(x)}  rate={cfg.RATE}")

# 1) 功率与频谱形状
seg = x[: int(cfg.RATE * 0.1)]
pwr = 10 * np.log10(np.mean(np.abs(seg) ** 2))
print(f"功率 {pwr:.1f} dBFS")

X = np.abs(np.fft.fftshift(np.fft.fft(seg))) ** 2
f = np.fft.fftshift(np.fft.fftfreq(len(seg), 1 / cfg.RATE))
# 分 10 段看频谱是否平坦
edges = np.linspace(-cfg.RATE / 2, cfg.RATE / 2, 11)
print("频谱（各段平均功率 dB）:")
for i in range(10):
    m = (f >= edges[i]) & (f < edges[i + 1])
    print(f"  {edges[i]/1e6:+.2f}~{edges[i+1]/1e6:+.2f} MHz: {10*np.log10(np.mean(X[m])):.1f}")

# 2) 相关峰：应是等间隔（frame_len=26368）的强峰
pre = oc.preamble_two()
b = np.conj(pre[::-1]).astype(np.complex64)
nfft = 1 << (len(seg) + len(b) - 2).bit_length()
R = np.fft.ifft(np.fft.fft(seg, nfft) * np.fft.fft(b, nfft))
absR = np.abs(R)
thr = 0.3 * absR.max()
cand = np.where(absR > thr)[0]
# 聚类：相邻索引合并
clusters = []
cur = [cand[0]]
for c in cand[1:]:
    if c - cur[-1] <= 64:
        cur.append(c)
    else:
        clusters.append(cur)
        cur = [c]
clusters.append(cur)
peaks = sorted([(int(c[np.argmax(absR[c])]), float(absR[c].max())) for c in clusters],
               key=lambda t: t[1], reverse=True)
print(f"\n相关峰 top8（位置, 幅度）:")
for p, a in peaks[:8]:
    print(f"  p={p}  peak={a:.3e}  start={p-len(pre)+1}  "
          f"start%frame={((p-len(pre)+1) % oc.frame_len())}")

# 峰间隔
if len(peaks) >= 3:
    pos = sorted([p for p, _ in peaks[:8]])
    diffs = np.diff(pos)
    print(f"峰间隔: {diffs}  (frame_len={oc.frame_len()})")
