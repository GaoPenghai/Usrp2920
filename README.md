# USRP 单板收发（自环）实验包

单板自环 = 同一台 USRP 全双工：`TX/RX` 口发射，`RX2` 口接收。
因此 **TX 和 RX 必须在同一个进程里跑**（UHD 不允许两个进程同时占用同一台 USRP）。

## 0. 前置检查（每次开机/换线后先跑一遍）

```bash
# 在 Atlas 上（davinci-mini）
ping -c 4 192.168.0.10          # 应 ~1 ms
uhd_find_devices                 # 应列出 serial 3168A18
```

如果 ping 报 `From 192.168.0.2 Destination Host Unreachable`，是 `usb0` 上挂着
`192.168.0.2/24` 抢了 USRP 网段的路由。删掉这个运行时地址即可（不改配置文件）：

```bash
sudo ip addr del 192.168.0.2/24 dev usb0
```

注意：**全部命令用 `/usr/bin/python3`**（3.10，带 uhd 绑定）；conda base 是 3.9，`import uhd` 会失败。

## 1. 上传

```cmd
scp -i C:\Users\gph13\.ssh\id_ed25519_dk_a2 -r D:\Xiangmu\usrp_loopback root@192.168.137.100:~/
```

板子上进入目录：

```bash
cd ~/usrp_loopback
```

## 2. 接线

```text
USRP 前面板：TX/RX 口 ──(≥30 dB 衰减器)── RX2 口
```

**没有衰减器不要直连**：TX 满功率直连 RX 会饱和甚至损伤接收前端。先低增益（TX 10 dB）起步。

## 3. 第 A 步：单音，验证链路和增益

```bash
/usr/bin/python3 loopback.py --wave tone --tx-gain 10 --rx-gain 35 --dur 1
/usr/bin/python3 analyze_tone.py
```

判断：

| 现象 | 处理 |
|---|---|
| 功率 > -5 dBFS | 降 `--rx-gain`（如 25）或加大衰减 |
| 功率 < -40 dBFS | 升 `--rx-gain`（如 45），或检查衰减器/接线 |
| 峰值频偏离 100 kHz 很多 | 检查 TX/RX 频点是否一致（默认都取 `cfg.FREQ`） |
| overflow > 0 | 降采样率或升主机缓冲（交接文档已调好 rmem，一般不会） |

目标：功率落在 **-20 ~ -10 dBFS**，峰值 ≈ +100 kHz，overflow=0。

## 4. 第 B 步：OFDM 帧自环

```bash
/usr/bin/python3 loopback.py --wave ofdm --tx-gain 10 --rx-gain 35 --dur 1
/usr/bin/python3 analyze_ofdm.py
```

输出解读：

- `BER` —— 误码率，任务书建议 ≤ 1×10⁻²（高信噪比受控条件）
- `EVM` —— 均衡后星座误差，越低越好（-15 dB 以下很好）
- `频偏估计` —— 同板 TX/RX 本振差，一般几 kHz 内
- `帧起点` —— 同步峰，若明显错乱说明信号太弱或波形不对

## 5. 接收端参数怎么跟着发射端调

`cfg.py` 里 **TX/RX 的 RATE 和 FREQ 是同一组**，`loopback.py` 强制两边一致，你不需要对齐它们。
真正要调的是 **接收增益**，依据第 A 步抓到的 dBFS：

| 实测 dBFS | 调法 |
|---|---|
| > -5 | 降 `--rx-gain` 5~10 dB，或加衰减 |
| -5 ~ -10 | 可接受，但建议再降一点 |
| -10 ~ -20 | 理想 |
| -20 ~ -40 | 可工作，但 BER 可能变差，可升 gain |
| < -40 | 升 `--rx-gain`，检查衰减器是否过大/接线 |

如果 BER 偏大，按顺序查：

1. **overflow 是否为 0**（loopback 输出里有）
2. **dBFS 是否在 -20 ~ -10**
3. **频偏估计** 是否异常大（> 10 kHz 说明约束不对）
4. 衰减器是否接反/松动
5. 采样率是否自己改过而没收敛（改 `--rate` 要确认 0 overflow，交接文档建议 12.5 Msps）

## 6. 常见报错

| 报错 | 原因 |
|---|---|
| `ModuleNotFoundError: uhd` | 用了 conda 的 python，改用 `/usr/bin/python3` |
| `No UHD Devices Found` | USRP 没上电/网线不在 eth0/路由被 usb0 抢了 |
| `RXMetadataErrorCode.overflow` | 采样率过高或主机处理慢，降 rate / 确保没有别的进程占设备 |
| 抓到的全是噪声 | TX 没在发（看 loopback 是否报 send 失败）或衰减过大 |

## 7. 归档（任务书 Week1/Week3 证据）

每次实验保留：

- `loopback.py` 打印的回读参数（rate/freq/gain）
- `analyze_tone.py` / `analyze_ofdm.py` 输出
- 需要时保留 `/dev/shm/*.npy`（磁盘紧张，别放 rootfs）

`test_sim.py` 是无硬件自检，换环境后可先跑它验证分析代码本身没问题：

```bash
/usr/bin/python3 test_sim.py
```
