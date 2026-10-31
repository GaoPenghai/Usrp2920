# -*- coding: utf-8 -*-
"""单板自环：同一台 USRP 全双工收发（TX/RX 口发，RX2 口收）。

用法（在 Atlas 上用 /usr/bin/python3 跑）：
  # 第一步：单音，验证链路和增益
  /usr/bin/python3 loopback.py --wave tone --tx-gain 10 --rx-gain 35 --dur 1

  # 第二步：OFDM 帧
  /usr/bin/python3 loopback.py --wave ofdm --tx-gain 10 --rx-gain 35 --dur 1

接线：USRP 前面板 TX/RX 口 --(>=30dB 衰减器)-- RX2 口。没有衰减器不要直连。
"""
import argparse
import threading
import time

import numpy as np
import uhd

import cfg
import ofdm_common as oc


def stream_args():
    sa = uhd.usrp.StreamArgs("fc32", "sc16")
    sa.channels = [0]
    return sa


def send_all(tx, samples, md):
    off = 0
    n = len(samples)
    while off < n:
        m = tx.send(samples[off:], md, 5.0)
        if m <= 0:
            return False
        off += m
    return True


def tx_worker(usrp, samples, stop):
    """TX 线程：循环发送同一段样点，直到主线程置位 stop。"""
    tx = usrp.get_tx_stream(stream_args())
    md = uhd.types.TXMetadata()
    md.has_time_spec = False
    first = True
    bursts = 0
    while not stop.is_set():
        md.start_of_burst = first
        md.end_of_burst = False
        if not send_all(tx, samples, md):
            break
        first = False
        bursts += 1
    md.end_of_burst = True
    try:
        tx.send(np.zeros(2048, np.complex64), md, 5.0)
    except Exception:
        pass
    return bursts


def main():
    ap = argparse.ArgumentParser(description="USRP 单板全双工自环")
    ap.add_argument("--wave", choices=["tone", "ofdm"], default="tone")
    ap.add_argument("--freq", type=float, default=cfg.FREQ)
    ap.add_argument("--rate", type=float, default=cfg.RATE)
    ap.add_argument("--tx-gain", type=float, default=cfg.TX_GAIN)
    ap.add_argument("--rx-gain", type=float, default=cfg.RX_GAIN)
    ap.add_argument("--dur", type=float, default=cfg.CAPTURE_SEC)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = args.out or (cfg.RX_FILE if args.wave == "ofdm" else cfg.TONE_FILE)

    print(f"[+] 打开 USRP {cfg.USRP_ADDR}")
    usrp = uhd.usrp.MultiUSRP("addr=" + cfg.USRP_ADDR)

    # ---- 共享参数：TX/RX 采样率与频点强制一致 ----
    usrp.set_tx_rate(args.rate, 0)
    usrp.set_rx_rate(args.rate, 0)
    usrp.set_tx_freq(args.freq, 0)
    usrp.set_rx_freq(args.freq, 0)
    usrp.set_tx_gain(args.tx_gain, 0)
    usrp.set_rx_gain(args.rx_gain, 0)
    try:
        usrp.set_tx_antenna(cfg.TX_ANT, 0)
        usrp.set_rx_antenna(cfg.RX_ANT, 0)
    except Exception as e:
        print(f"[!] 设置天线失败（可忽略）: {e}")

    # ---- 回读：确认参数真的生效 ----
    print(f"[+] 回读 TX: rate={usrp.get_tx_rate(0):.3e} "
          f"freq={usrp.get_tx_freq(0):.6e} gain={usrp.get_tx_gain(0)}")
    print(f"[+] 回读 RX: rate={usrp.get_rx_rate(0):.3e} "
          f"freq={usrp.get_rx_freq(0):.6e} gain={usrp.get_rx_gain(0)}")
    if args.wave == "tone":
        print(f"[+] 波形: 单音 offset={cfg.TONE_OFFSET_HZ/1e3:.0f} kHz")
        samples = oc.make_tone()
    else:
        print(f"[+] 波形: OFDM 帧 ({oc.frame_len()} 样点/帧)")
        samples, bits = oc.build_ofdm_frame()
        oc.save_tx_meta(bits)
        print(f"[+] 已存 TX 元数据: {cfg.TX_META}")

    # ---- 启动 TX 线程 ----
    print("[+] 启动 TX ...")
    stop = threading.Event()
    tx_thread = threading.Thread(target=tx_worker, args=(usrp, samples, stop), daemon=True)
    tx_thread.start()
    time.sleep(0.5)   # 让 TX 先跑起来

    # ---- RX 抓取 ----
    rx = usrp.get_rx_stream(stream_args())
    num = int(args.rate * args.dur)
    buf = np.zeros(num, np.complex64)

    cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
    cmd.num_samps = num
    cmd.stream_now = True
    rx.issue_stream_cmd(cmd)

    md = uhd.types.RXMetadata()
    got = 0
    overflow = 0
    t0 = time.time()
    print(f"[+] RX 抓取 {num} 点（{args.dur:.1f} s）...")
    while got < num:
        n = rx.recv(buf[got:], md, 5.0)
        if n == 0:
            print("[!] recv 超时，提前结束")
            break
        got += n
        if "overflow" in str(md.error_code):
            overflow += 1
    elapsed = time.time() - t0

    # ---- 停止 TX ----
    stop.set()
    tx_thread.join(timeout=5.0)

    # ---- 结果 ----
    if got == 0:
        print("[!] 没抓到任何样点，检查设备与接线")
        return
    x = buf[:got]
    pwr = 10 * np.log10(np.mean(np.abs(x) ** 2) + 1e-12)
    np.save(out, x)
    print(f"[+] 抓到 {got} 点，用时 {elapsed:.2f} s，overflow={overflow}")
    print(f"[+] 采样功率 = {pwr:.1f} dBFS  (目标 -20 ~ -10，> -5 有饱和风险)")
    print(f"[+] 已保存 {out}")


if __name__ == "__main__":
    main()
