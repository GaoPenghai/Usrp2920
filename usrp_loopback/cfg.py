# -*- coding: utf-8 -*-
"""单板自环实验共享参数：TX / RX 必须一致的参数都在这里。

接收端参数说明：
- RATE / FREQ 与发射端强制一致（脚本保证），你只调 RX_GAIN。
- RX_GAIN 依据抓到的功率调：目标 -20 ~ -10 dBFS，超过 -5 会饱和。
"""

USRP_ADDR = "192.168.0.10"   # 交接文档实测地址（不是出厂 192.168.10.2）

# ---- 共享参数（TX 与 RX 必须一致）----
RATE       = 12.5e6     # 采样率；交接文档建议工作点 12.5 Msps（抽取 8，半带+CIC 完整）
FREQ       = 915e6      # 中心频率；WBX v4 范围 25–2200 MHz，确认实验室频段许可后再改
FFT_SIZE   = 1024
CP_LEN     = 128        # 1/8
GUARD      = 64         # 两侧保护子载波
N_DATA_SYM = 20         # 每帧数据 OFDM 符号数
PILOT_STEP = 8          # 每 8 个有效子载波放一个导频（comb）
GAP_SAMPS  = 1024       # 前导与数据之间的静默样点
TONE_OFFSET_HZ = 100e3  # 单音模式相对中心频率的偏移

# ---- 发射端 ----
TX_GAIN = 10.0          # dB，起步值；务必先接 30 dB 衰减器
TX_ANT  = "TX/RX"

# ---- 接收端（依据发射端实测再调）----
RX_GAIN = 35.0          # dB，起步值
RX_ANT  = "RX2"

# ---- 文件（磁盘只剩 ~4.7 G，IQ 一律写 /dev/shm）----
RX_FILE = "/dev/shm/rx_capture.npy"
TX_META = "/dev/shm/tx_meta.npz"
TONE_FILE = "/dev/shm/rx_tone.npy"

# ---- 抓取时长（秒）----
CAPTURE_SEC = 1.0
