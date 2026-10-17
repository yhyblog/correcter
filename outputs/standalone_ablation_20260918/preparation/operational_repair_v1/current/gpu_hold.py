#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time


def parse_devices(value):
    if value == "all":
        import torch

        return list(range(torch.cuda.device_count()))
    return [int(item) for item in value.split(",") if item.strip()]


def resolve_dtype(name):
    import torch

    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    if name == "fp32":
        return torch.float32
    raise ValueError(f"unsupported dtype: {name}")


def pid_is_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def daemonize(args):
    if os.path.exists(args.pid_file):
        with open(args.pid_file, "r", encoding="utf-8") as handle:
            old_pid_text = handle.read().strip()
        if old_pid_text:
            old_pid = int(old_pid_text)
            if pid_is_alive(old_pid):
                print(f"already running: pid {old_pid}")
                return 0

    cmd = [
        sys.executable,
        os.path.abspath(__file__),
        "--devices",
        args.devices,
        "--size",
        str(args.size),
        "--dtype",
        args.dtype,
        "--log-interval",
        str(args.log_interval),
        "--target-util",
        str(args.target_util),
        "--period-seconds",
        str(args.period_seconds),
    ]
    if args.sleep_ms:
        cmd.extend(["--sleep-ms", str(args.sleep_ms)])

    log = open(args.log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    with open(args.pid_file, "w", encoding="utf-8") as handle:
        handle.write(f"{proc.pid}\n")
    print(f"started pid {proc.pid}")
    print(f"log: {os.path.abspath(args.log_file)}")
    print(f"stop: kill -TERM -{proc.pid}")
    return 0


def worker(
    device,
    size,
    dtype_name,
    sleep_ms,
    target_util,
    period_seconds,
    stop_event,
    log_interval,
):
    import torch

    torch.cuda.set_device(device)
    torch.backends.cuda.matmul.allow_tf32 = True
    dtype = resolve_dtype(dtype_name)
    dev = torch.device(f"cuda:{device}")

    a = torch.randn((size, size), device=dev, dtype=dtype)
    b = torch.randn((size, size), device=dev, dtype=dtype)
    c = torch.empty((size, size), device=dev, dtype=dtype)
    buffers = [a, b, c]

    for _ in range(8):
        torch.mm(buffers[0], buffers[1], out=buffers[2])
    torch.cuda.synchronize(dev)

    iterations = 0
    last_log = time.monotonic()
    print(f"device {device}: running size={size} dtype={dtype_name}", flush=True)

    while not stop_event.is_set():
        cycle_start = time.monotonic()
        active_until = cycle_start + period_seconds * target_util

        while not stop_event.is_set():
            x = buffers[iterations % 3]
            y = buffers[(iterations + 1) % 3]
            z = buffers[(iterations + 2) % 3]
            torch.mm(x, y, out=z)
            iterations += 1

            if target_util < 1.0 or sleep_ms:
                torch.cuda.synchronize(dev)
            if target_util < 1.0 and time.monotonic() >= active_until:
                break
            if target_util >= 1.0:
                break

        if target_util < 1.0:
            idle = period_seconds - (time.monotonic() - cycle_start)
            if idle > 0:
                stop_event.wait(idle)
        elif sleep_ms:
            stop_event.wait(sleep_ms / 1000.0)

        now = time.monotonic()
        if now - last_log >= log_interval:
            torch.cuda.synchronize(dev)
            print(f"device {device}: iterations={iterations}", flush=True)
            last_log = now

    torch.cuda.synchronize(dev)
    print(f"device {device}: stopped iterations={iterations}", flush=True)


def run(args):
    devices = parse_devices(args.devices)
    if not devices:
        raise SystemExit("no CUDA devices selected")

    ctx = mp.get_context("spawn")
    stop_event = ctx.Event()
    children = []

    def handle_signal(signum, _frame):
        print(f"received signal {signum}, stopping", flush=True)
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    for device in devices:
        proc = ctx.Process(
            target=worker,
            args=(
                device,
                args.size,
                args.dtype,
                args.sleep_ms,
                args.target_util,
                args.period_seconds,
                stop_event,
                args.log_interval,
            ),
        )
        proc.start()
        children.append(proc)

    while any(proc.is_alive() for proc in children):
        for proc in children:
            proc.join(timeout=1.0)
        if stop_event.is_set():
            break

    stop_event.set()
    for proc in children:
        if proc.is_alive():
            proc.terminate()
    for proc in children:
        proc.join(timeout=10.0)


def main():
    parser = argparse.ArgumentParser(description="Keep selected CUDA GPUs busy with GEMM loops.")
    parser.add_argument("--devices", default="all", help="'all' or comma-separated CUDA device indexes")
    parser.add_argument("--size", type=int, default=16384, help="square matrix size per GPU")
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"), default="bf16")
    parser.add_argument("--sleep-ms", type=float, default=0.0, help="optional pause after each matmul")
    parser.add_argument(
        "--target-util",
        type=float,
        default=1.0,
        help="target GPU active duty cycle in (0, 1]",
    )
    parser.add_argument(
        "--period-seconds",
        type=float,
        default=0.2,
        help="duty-cycle period used when --target-util is below 1",
    )
    parser.add_argument("--log-interval", type=float, default=30.0)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--pid-file", default="gpu_hold.pid")
    parser.add_argument("--log-file", default="gpu_hold.log")
    args = parser.parse_args()

    if not 0 < args.target_util <= 1:
        parser.error("--target-util must be in (0, 1]")
    if args.period_seconds <= 0:
        parser.error("--period-seconds must be positive")

    if args.daemon:
        raise SystemExit(daemonize(args))
    run(args)


if __name__ == "__main__":
    main()
