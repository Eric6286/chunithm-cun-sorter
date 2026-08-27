# -*- coding: utf-8 -*-
"""本机的小 HTTP/SSE 服务，把内存读到的判定数据发给 DGHub 插件。

分工和 Chuni2Api 一致：**cun 只出数据，触发在插件里做**。波形预设、强度、
通道、时长全在 DGHub 插件自己的配置页，这边一个都不管。

* ``/events``：SSE 流。每 100ms 推一次判定计数快照，结算时额外推一条
  带寸判定结果的 ``settle`` 事件。
* ``/data``：当前快照的一次性 JSON。
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .models import JudgeCounts

#: SSE 快照推送间隔
SNAPSHOT_INTERVAL_SEC = 0.1
#: 这么久没有新的判定数据就报 WAITING
STALE_AFTER_SEC = 2.0

StatusFn = Callable[[str], None]


class _QuietServer(ThreadingHTTPServer):
    """插件断开连接是常态，别为此往 stderr 打整段 traceback。

    ``ThreadingHTTPServer`` 默认会把每个连接异常打出来。DGHub 插件重连、
    用户关掉插件、SSE 流被中断，每一次都会刷一屏，把真正的错误淹掉。
    """

    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, TimeoutError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class LinkServer:
    """联动数据服务。:meth:`start` / :meth:`stop` 之间一直听着。"""

    def __init__(self, on_status: StatusFn) -> None:
        self._on_status = on_status
        self._lock = threading.Lock()
        self._counts = JudgeCounts()
        self._last_tick = 0.0
        self._queues: list[queue.SimpleQueue[str]] = []
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def _status(self, msg: str) -> None:
        try:
            self._on_status(msg)
        except Exception:                           # noqa: BLE001
            pass

    def start(self, port: int) -> None:
        if self.running:
            return
        try:
            handler = _make_handler(self)
            self._httpd = _QuietServer(("127.0.0.1", port), handler)
            self._thread = threading.Thread(
                target=self._httpd.serve_forever, name="cun-link", daemon=True)
            self._thread.start()
            self._status(f"监听 127.0.0.1:{port}，等待插件连接")
        except OSError as e:
            self._httpd = None
            self._status(f"启动失败（端口 {port} 被占用？）：{e}")

    def stop(self) -> None:
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        t, self._thread = self._thread, None
        if t is not None and t.is_alive():
            t.join(timeout=3.0)
        with self._lock:
            self._queues.clear()

    # ----------------------------- 数据 -------------------------------------
    def update_counts(self, counts: JudgeCounts) -> None:
        """喂最新的计数（内存读取线程，约 20Hz）。"""
        with self._lock:
            self._counts = counts
            self._last_tick = time.monotonic()

    def publish_settle(self, payload: dict[str, Any]) -> None:
        """把结算事件广播给所有连上的客户端。"""
        data = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            for q in self._queues:
                q.put(data)

    def snapshot_json(self) -> str:
        with self._lock:
            stale = (time.monotonic() - self._last_tick) > STALE_AFTER_SEC
            c = self._counts
        status = "WAITING" if stale else ("IN MENU" if c.total == 0 else "PLAYING")
        return json.dumps({
            "critical": c.critical, "justice": c.justice,
            "attack": c.attack, "miss": c.miss, "status": status,
        }, ensure_ascii=False)

    # ----------------------------- 客户端登记 -------------------------------
    def _register(self) -> queue.SimpleQueue[str]:
        q: queue.SimpleQueue[str] = queue.SimpleQueue()
        with self._lock:
            self._queues.append(q)
            n = len(self._queues)
        self._status(f"插件已连接 ×{n}")
        return q

    def _unregister(self, q: queue.SimpleQueue[str]) -> None:
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass
            n = len(self._queues)
        self._status(f"插件已连接 ×{n}" if n > 0 else "插件已断开，等待连接")


_HELP = ("今天你寸了吗 · DGHub 联动服务\n"
         "/events = SSE 判定流\n"
         "/data = 当前快照\n")


def _make_handler(server: LinkServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: Any) -> None:
            pass                                    # 别往 stderr 刷访问日志

        def do_GET(self) -> None:                   # noqa: N802 - BaseHTTPRequestHandler 的约定
            path = self.path.split("?", 1)[0]
            if path.startswith("/events"):
                self._serve_sse()
            elif path.startswith("/data"):
                self._write_simple("application/json", server.snapshot_json())
            else:
                self._write_simple("text/plain; charset=utf-8", _HELP)

        def _write_simple(self, content_type: str, body: str) -> None:
            data = body.encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                pass                                # 客户端跑了

        def _serve_sse(self) -> None:
            # SSE 不带 Content-Length，body 到连接关闭为止；这条连接不复用。
            self.close_connection = True
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
            except OSError:
                return

            q = server._register()                  # noqa: SLF001 - 同模块内的协作
            try:
                while server.running:
                    while True:
                        try:
                            evt = q.get_nowait()
                        except queue.Empty:
                            break
                        self.wfile.write(f"data: {evt}\n\n".encode())
                    self.wfile.write(f"data: {server.snapshot_json()}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(SNAPSHOT_INTERVAL_SEC)
            except OSError:
                pass                                # 插件断开
            finally:
                server._unregister(q)               # noqa: SLF001

    return Handler
