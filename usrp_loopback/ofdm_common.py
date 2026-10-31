# -*- coding: utf-8 -*-
"""OFDM 帧结构定义：TX 与 RX 共用，保证两端对帧的理解完全一致。

帧结构（样点）：
  preamble       2 x (FFT+CP)     两个相同的 OFDM 符号（Schmidl-Cox 风格，用于同步）
  gap            GAP_SAMPS        静默样点
  data           N_DATA_SYM x (FFT+CP)   QPSK 数据符号，导频每 PILOT_STEP 个子载波一个
"""
import numpy as np
import cfg

N = cfg.FFT_SIZE
CP = cfg.CP_LEN

_k = np.arange(N)
_valid = (_k > cfg.GUARD) & (_k < N - cfg.GUARD) & (_k != N // 2)
VALID_IDX = _k[_valid]                      # 有效子载波（升序）
PILOT_IDX = VALID_IDX[::cfg.PILOT_STEP]     # 导频子载波
DATA_IDX = np.setdiff1d(VALID_IDX, PILOT_IDX)  # 数据子载波


def _ofdm_symbol(X):
    """频域 X -> 加 CP 的时域符号"""
    x = np.fft.ifft(X) * np.sqrt(N)
    return np.concatenate([x[-CP:], x])


def preamble_two():
    """两个相同的前导 OFDM 符号（BPSK 频域随机序列，固定种子）"""
    rng = np.random.default_rng(20261031)
    X = np.zeros(N, dtype=complex)
    X[VALID_IDX] = rng.choice([-1.0, 1.0], size=len(VALID_IDX))
    s = _ofdm_symbol(X)
    return np.concatenate([s, s])


def build_ofdm_frame():
    """生成一帧 OFDM 样点 + 对应的已知比特（按子载波顺序，re 在前 im 在后）"""
    rng = np.random.default_rng(7)
    n_sub = len(DATA_IDX)
    n_bits = n_sub * 2 * cfg.N_DATA_SYM
    bits = rng.integers(0, 2, n_bits).astype(np.uint8)

    syms = []
    for i in range(cfg.N_DATA_SYM):
        b = bits[2 * n_sub * i: 2 * n_sub * (i + 1)]
        re = 1 - 2 * b[0::2].astype(np.float64)
        im = 1 - 2 * b[1::2].astype(np.float64)
        X = np.zeros(N, dtype=complex)
        X[PILOT_IDX] = 1.0 + 0.0j                 # 导频：已知 QPSK 点
        X[DATA_IDX] = (re + 1j * im) / np.sqrt(2.0)  # QPSK
        syms.append(_ofdm_symbol(X))

    gap = np.zeros(cfg.GAP_SAMPS, dtype=complex)
    frame = np.concatenate([preamble_two(), gap] + syms).astype(np.complex64)
    # USRP sc16 满量程为 1.0；OFDM 峰均比大，按峰值缩放到 0.7 防止 DAC 削波
    peak = float(np.max(np.abs(frame)))
    if peak > 0.7:
        frame = (frame * (0.7 / peak)).astype(np.complex64)
    return frame, bits


def preamble_len():
    return len(preamble_two())


def frame_len():
    return 2 * (N + CP) + cfg.GAP_SAMPS + cfg.N_DATA_SYM * (N + CP)


def save_tx_meta(bits):
    np.savez(cfg.TX_META,
             bits=bits,
             frame_len=frame_len(),
             preamble_len=preamble_len())


def make_tone():
    """单音波形（相对中心频率 +TONE_OFFSET_HZ），幅度 0.3"""
    n = int(cfg.RATE)  # 1 秒
    t = np.arange(n) / cfg.RATE
    x = 0.3 * np.exp(2j * np.pi * cfg.TONE_OFFSET_HZ * t)
    return x.astype(np.complex64)
