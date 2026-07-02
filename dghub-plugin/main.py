"""DGHub 插件 — 「今天你寸了吗」联动。

连接 cun 的本地 SSE 数据端点（cun「配置 → DGHub 联动」开启，默认
http://127.0.0.1:8890/events），两类事件：

  - 判定计数流 {"critical","justice","attack","miss","status"}
    → 打歌中 MISS / ATTACK 增加时实时触发（各自开关 + 强度）
  - 结算事件 {"event":"settle","cun":bool,"rules","score","rank",...}
    → cun 按用户自建「寸」规则判定；寸了则触发结算波形

触发行为（强度 / 波形预设 / 通道 / 持续时间）全部在本插件的 DGHub
配置页调节；cun 侧只提供数据。基于 DGHub 官方 demo_external 与
Chuni2Api DGLAB 示例改写。依赖：websockets（DGHub 主程序环境自带）。
"""

import asyncio
import json
import os
import socket
import sys
import threading
import urllib.request

try:
    import websockets
except ImportError:
    print("缺少 websockets（DGHub 主程序环境应自带）", file=sys.stderr)
    raise


async def main() -> None:
    host = os.environ["DGHUB_HOST"]
    port = os.environ["DGHUB_PORT"]
    token = os.environ["DGHUB_TOKEN"]

    # ── 配置（由 DGHub 推送，键与 manifest.config_schema 一致） ──
    cfg = {
        "endpoint": "http://127.0.0.1:8890/events",
        "debug": False,
        "miss_enabled": True,
        "miss_strength": 30,
        "attack_enabled": False,
        "attack_strength": 15,
        "rt_duration": 1.5,
        "rt_preset": "CS2-受伤",
        "channel": "both",
        "settle_enabled": True,
        "settle_strength": 50,
        "settle_duration": 3.0,
        "settle_preset": "CS2-受伤",
    }

    loop = asyncio.get_running_loop()
    sse_queue: asyncio.Queue = asyncio.Queue()

    # ── SSE 后台读取线程（阻塞 IO → 入队 asyncio） ──
    sse_stop = threading.Event()
    sse_lock = threading.Lock()
    sse_thread = [None]
    sse_resp = [None]

    def sse_read(endpoint: str) -> None:
        try:
            req = urllib.request.Request(endpoint)
            req.add_header("Accept", "text/event-stream")
            req.add_header("Cache-Control", "no-cache")
            resp = urllib.request.urlopen(req, timeout=10)
            sock = resp.fp.raw._sock if hasattr(resp.fp, "raw") else None
            if sock:
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass
            with sse_lock:
                sse_resp[0] = resp
            buf = b""
            reader = resp.fp.read1 if hasattr(resp.fp, "read1") else lambda n: resp.read(n)
            loop.call_soon_threadsafe(sse_queue.put_nowait, {"_connected": endpoint})
            while not sse_stop.is_set():
                try:
                    chunk = reader(256)
                except Exception:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n\n" in buf:
                    raw, buf = buf.split(b"\n\n", 1)
                    for line in raw.split(b"\n"):
                        if line.startswith(b"data: "):
                            try:
                                obj = json.loads(line[6:].decode("utf-8", errors="replace"))
                                loop.call_soon_threadsafe(sse_queue.put_nowait, obj)
                            except json.JSONDecodeError:
                                pass
            if not sse_stop.is_set():
                loop.call_soon_threadsafe(sse_queue.put_nowait, {"_error": "连接断开"})
        except Exception as exc:
            loop.call_soon_threadsafe(sse_queue.put_nowait, {"_error": str(exc)})
        finally:
            with sse_lock:
                sse_resp[0] = None

    def sse_start(endpoint: str) -> None:
        sse_stop.clear()
        t = threading.Thread(target=sse_read, args=(endpoint,), daemon=True)
        sse_thread[0] = t
        t.start()

    def sse_stopper() -> None:
        sse_stop.set()
        with sse_lock:
            r = sse_resp[0]
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
                sse_resp[0] = None
        t = sse_thread[0]
        if t is not None and t.is_alive():
            t.join(timeout=3)

    # ── 状态上报（启动检查 + 悬浮窗状态卡片） ──
    async def report(ws, source_state: str, source_detail: str, display: str) -> None:
        await ws.send(json.dumps({
            "op": "status",
            "fields": {
                "display_status": display,
                "startup_check": {
                    "title": "寸联动启动检查",
                    "steps": [
                        {"key": "plugin", "title": "插件进程", "state": "ok",
                         "detail": "已连接 DGHub"},
                        {"key": "cun", "title": "cun 数据服务", "state": source_state,
                         "detail": source_detail,
                         "hint": "打开「今天你寸了吗」，在 配置 → DGHub 联动 开启并保存"},
                    ],
                },
            },
        }))

    # ── 事件处理协程 ──
    state = {"last": None}          # 上一帧计数 dict，None = 等待基线

    async def trigger(ws, pct: int, duration: float, preset: str, label: str) -> None:
        if pct <= 0:
            return
        await ws.send(json.dumps({
            "op": "trigger",
            "action": "both",
            "delta_pct": max(-100, min(100, int(pct))),
            "strength_mode": "rollback",
            "duration_s": max(0.0, min(300.0, float(duration))),
            "preset": preset,
            "channel": cfg["channel"],
            "label": label,
        }))
        if cfg["debug"]:
            await ws.send(json.dumps({
                "op": "log", "level": "debug",
                "message": f"TRIGGER {label} | {pct}% {duration}s {preset} ch={cfg['channel']}",
            }))

    async def on_counts(ws, evt: dict) -> None:
        status = evt.get("status", "")
        if status != "PLAYING":
            state["last"] = None
            return
        last = state["last"]
        state["last"] = evt
        if last is None:            # 中途接入：先建基线，不触发
            return
        d_miss = evt.get("miss", 0) - last.get("miss", 0)
        d_atk = evt.get("attack", 0) - last.get("attack", 0)
        if d_miss > 0 and cfg["miss_enabled"]:
            await trigger(ws, cfg["miss_strength"], cfg["rt_duration"], cfg["rt_preset"],
                          f"MISS ×{evt.get('miss', 0)}")
        elif d_atk > 0 and cfg["attack_enabled"]:
            await trigger(ws, cfg["attack_strength"], cfg["rt_duration"], cfg["rt_preset"],
                          f"ATTACK ×{evt.get('attack', 0)}")

    async def on_settle(ws, evt: dict) -> None:
        score = evt.get("score", 0)
        rank = evt.get("rank", "?")
        summary = f"{score} {rank} A{evt.get('attack', 0)}M{evt.get('miss', 0)}"
        if evt.get("cun"):
            rules = evt.get("rules", "寸")
            if cfg["settle_enabled"]:
                await trigger(ws, cfg["settle_strength"], cfg["settle_duration"],
                              cfg["settle_preset"], f"寸了！{rules} {summary}")
            await ws.send(json.dumps({
                "op": "log", "level": "info",
                "message": f"结算：寸了（{rules}）{summary}",
            }))
        elif cfg["debug"]:
            await ws.send(json.dumps({
                "op": "log", "level": "debug", "message": f"结算：未寸 {summary}",
            }))

    async def sse_processor(ws) -> None:
        while True:
            evt = await sse_queue.get()
            if "_connected" in evt:
                await report(ws, "ok", "已连接 cun 数据流", "已连接，等待游戏")
                continue
            if "_error" in evt:
                state["last"] = None
                await report(ws, "pending", f"未连上 cun（{evt['_error']}），5 秒后重连",
                             "等待 cun 数据服务")
                await asyncio.sleep(5)
                sse_start(cfg["endpoint"])
                continue
            if evt.get("event") == "settle":
                await on_settle(ws, evt)
            else:
                await on_counts(ws, evt)

    # ── WebSocket 主循环 ──
    uri = f"ws://{host}:{port}/ws/plugin?token={token}"
    async with websockets.connect(uri) as ws:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json"),
                  encoding="utf-8") as f:
            manifest = json.load(f)
        await ws.send(json.dumps({"op": "hello", "token": token, "manifest": manifest}))
        ack = json.loads(await ws.recv())
        if not ack.get("accepted"):
            raise RuntimeError(ack.get("reason", "hello rejected"))

        await report(ws, "pending", "等待 cun 数据服务", "等待 cun")
        sse_task = asyncio.create_task(sse_processor(ws))

        try:
            async for raw in ws:
                msg = json.loads(raw)
                op = msg.get("op")
                if op == "stop":
                    break
                if op == "config":
                    for k in cfg:
                        if k in msg.get("data", {}):
                            cfg[k] = msg["data"][k]
                    if sse_thread[0] is None:
                        sse_start(cfg["endpoint"])
                elif op == "config_changed":
                    key, val = msg.get("key"), msg.get("value")
                    if key in cfg:
                        cfg[key] = val
                        if key == "endpoint":
                            sse_stopper()
                            sse_start(cfg["endpoint"])
                elif op == "ping":
                    await ws.send(json.dumps({"op": "pong", "t": msg.get("t")}))
        finally:
            sse_task.cancel()
            try:
                await sse_task
            except asyncio.CancelledError:
                pass
            sse_stopper()


if __name__ == "__main__":
    asyncio.run(main())
