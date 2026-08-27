# -*- coding: utf-8 -*-
"""直接从游戏进程读四个判定计数（JC / JUSTICE / ATTACK / MISS）。

做法移植自 [Chuni2Api](https://github.com/iyxddw/Chuni2Api)：在已提交的堆区域里
搜 ``NUM_xxx\\0`` 这几个字段名字符串，命中处 +0x238 就是计数值（+0x234 处有个
``03 00 00 00`` 的标记做校验）。

计数块在一首歌结束时会被释放，所以「读失败」本身就是结算信号（原地清零也
按同样处理）。**全程只读**，不写游戏内存、不注入、不 hook。
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from . import winapi
from .models import JudgeCounts

VALUE_OFFSET = 0x238
SCAN_MIN_ADDR = 0x5000_0000
SCAN_MAX_ADDR = 0xFFFF_0000         # 目标是 32 位进程，扫到 4GB 以下就够
MAX_HITS = 3
POLL_SEC = 0.05                     # 20Hz，和上游一致
RESCAN_DELAY_SEC = 1.5
WAIT_GAME_SEC = 2.0
#: 音符数少于这个就不当一次有效结算（中途退出 / 垃圾数据）
MIN_NOTES_FOR_SETTLE = 10
#: 计数值超过这个一律当 0，和上游一样的脏数据兜底
MAX_SANE_COUNT = 30000

CHUNK_SIZE = 1 << 20                # 1MB 读窗口

MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
_READABLE_PROT = frozenset({0x02, 0x04, 0x20, 0x40})

_MARKER = b"\x03\x00\x00\x00"
_SIGS: tuple[bytes, ...] = (
    b"NUM_jctirical\0",
    b"NUM_ctirical\0",
    b"NUM_attack\0",
    b"NUM_miss\0",
)

StatusFn = Callable[[str], None]
DeltaFn = Callable[[JudgeCounts, JudgeCounts], None]
SongEndFn = Callable[[JudgeCounts], None]
TickFn = Callable[[JudgeCounts], None]


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    """64 位调用方看到的 ``MEMORY_BASIC_INFORMATION``（两个对齐洞要写出来）。"""

    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wintypes.DWORD),
        ("__alignment1", wintypes.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("__alignment2", wintypes.DWORD),
    ]


class JudgeMemoryReader:
    """后台线程：连上游戏 → 定位地址 → 20Hz 读数 → 结算时回调。"""

    def __init__(self, get_process_name: Callable[[], str], on_status: StatusFn,
                 on_delta: DeltaFn, on_song_end: SongEndFn,
                 on_tick: TickFn | None = None) -> None:
        self._get_process_name = get_process_name
        self._on_status = on_status
        self._on_delta = on_delta
        self._on_song_end = on_song_end
        self._on_tick = on_tick
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cun-judge", daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 3.0) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=join_timeout)
        self._thread = None

    # ----------------------------- 主循环 -----------------------------------
    def _status(self, msg: str) -> None:
        try:
            self._on_status(msg)
        except Exception:                           # noqa: BLE001 - 界面回调不能拖垮读取
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            name = (self._get_process_name() or "").strip() or "chusanApp.exe"
            pid = winapi.pid_of(name)
            if pid == 0:
                self._status("等待游戏进程…")
                if self._stop.wait(WAIT_GAME_SEC):
                    return
                continue

            handle = winapi.kernel32.OpenProcess(
                winapi.PROCESS_VM_READ | winapi.PROCESS_QUERY_INFORMATION, False, pid)
            if not handle:
                self._status("无法打开游戏进程（权限不足？）")
                if self._stop.wait(5.0):
                    return
                continue
            try:
                self._read_loop(handle, pid)
            finally:
                winapi.kernel32.CloseHandle(handle)

    def _read_loop(self, handle: int, pid: int) -> None:
        """一个进程生命周期内的「扫描 → 轮询」循环。"""
        self._status("已连接游戏，扫描判定地址…")
        addrs: list[int] | None = None

        while not self._stop.is_set():
            # 先试着复验上次的地址——计数块能跨曲存活，能省掉一次全区扫描
            if addrs is None or not _revalidate(handle, addrs):
                addrs = self._find_fields(handle)
                if addrs is None:
                    if not winapi.is_process_alive(pid):
                        self._status("游戏已退出")
                        return
                    self._status("未找到判定数据（菜单/加载中），稍后重扫…")
                    if self._stop.wait(RESCAN_DELAY_SEC):
                        return
                    continue
                self._status("判定地址已锁定，实时读取中")

            prev = JudgeCounts()
            has_prev = False
            last_playing = JudgeCounts()
            played = False

            while not self._stop.is_set():
                cur = _read_counts(handle, addrs)
                if cur is None:
                    # 内存被释放＝这首歌结束了，先结算再重扫
                    played = self._settle_if_played(played, last_playing)
                    addrs = None
                    if not winapi.is_process_alive(pid):
                        self._status("游戏已退出")
                        return
                    break

                if self._on_tick is not None:
                    try:
                        self._on_tick(cur)
                    except Exception:               # noqa: BLE001
                        pass

                if cur.total == 0:
                    # 原地清零：回菜单了，或者曲间计数块被复用而不是释放
                    played = self._settle_if_played(played, last_playing)
                    has_prev = False
                else:
                    if has_prev and (cur.miss > prev.miss or cur.attack > prev.attack
                                     or cur.critical > prev.critical or cur.justice > prev.justice):
                        try:
                            self._on_delta(prev, cur)
                        except Exception:           # noqa: BLE001
                            pass
                    prev = cur
                    has_prev = True
                    last_playing = cur
                    played = True

                if self._stop.wait(POLL_SEC):
                    return

    def _settle_if_played(self, played: bool, last: JudgeCounts) -> bool:
        """打过才结算。返回新的 ``played`` 状态（永远是 ``False``）。"""
        if not played:
            return False
        if last.total >= MIN_NOTES_FOR_SETTLE:
            try:
                self._on_song_end(last)
            except Exception:                       # noqa: BLE001
                pass
        return False

    # ----------------------------- 签名扫描 ---------------------------------
    def _find_fields(self, handle: int) -> list[int] | None:
        """遍历 ≥0x50000000 的已提交可读区域，找那四个签名。

        返回四个计数值的地址（同一签名有多个实例时取**最高**那个，
        跟上游一致：堆上的运行时实例地址比模块里的静态串高）；找不全返回 ``None``。
        """
        hits: list[set[int]] = [set(), set(), set(), set()]
        # 标记落在 sig+0x234..0x238，分块之间要留这么多重叠，
        # 免得跨块的匹配校验不到
        tail = VALUE_OFFSET + max(len(s) for s in _SIGS)
        chunk = ctypes.create_string_buffer(CHUNK_SIZE)

        addr = 0
        mbi = MEMORY_BASIC_INFORMATION64()
        mbi_size = ctypes.sizeof(mbi)
        while addr < SCAN_MAX_ADDR and not self._stop.is_set():
            got = winapi.kernel32.VirtualQueryEx(
                handle, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size)
            if got == 0:
                addr += 0x1000
                continue
            base = int(mbi.BaseAddress)
            size = int(mbi.RegionSize)
            nxt = base + size if size > 0 else addr + 0x1000

            readable = (mbi.State == MEM_COMMIT and size > 0
                        and not (mbi.Protect & PAGE_GUARD)
                        and (mbi.Protect & 0xFF) in _READABLE_PROT)
            if readable and base >= SCAN_MIN_ADDR:
                if all(len(h) >= MAX_HITS for h in hits):
                    break
                _scan_region(handle, base, size, chunk, tail, hits)
            addr = nxt if nxt > addr else addr + 0x1000

        if any(not h for h in hits):
            return None
        return [max(h) for h in hits]


def _scan_region(handle: int, base: int, size: int, chunk: ctypes.Array,
                 tail: int, hits: list[set[int]]) -> None:
    """在一个内存区域里逐块找签名。"""
    offset = 0
    read = ctypes.c_size_t(0)
    while offset < size:
        want = min(CHUNK_SIZE, size - offset)
        ok = winapi.kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(base + offset), chunk, want, ctypes.byref(read))
        got = read.value
        if not ok or got == 0:
            return                                  # 区域在扫描途中消失了
        data = chunk.raw[:got]

        for si, sig in enumerate(_SIGS):
            if len(hits[si]) >= MAX_HITS:
                continue
            start = 0
            while len(hits[si]) < MAX_HITS:
                pos = data.find(sig, start)
                if pos < 0:
                    break
                marker_off = pos + VALUE_OFFSET - 4
                if marker_off + 4 <= len(data) and data[marker_off:marker_off + 4] == _MARKER:
                    hits[si].add(base + offset + pos + VALUE_OFFSET)
                start = pos + 1

        if got < want or offset + got >= size or got <= tail:
            return
        offset += got - tail                        # 回退一点，跨块的匹配下一轮还能命中


def _read_counts(handle: int, addrs: list[int]) -> JudgeCounts | None:
    """读四个计数。任一处读失败就返回 ``None``（＝计数块没了）。"""
    buf = ctypes.create_string_buffer(2)
    read = ctypes.c_size_t(0)
    values = []
    for a in addrs:
        ok = winapi.kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(a), buf, 2, ctypes.byref(read))
        if not ok or read.value != 2:
            return None
        v = buf.raw[0] | (buf.raw[1] << 8)
        values.append(0 if v > MAX_SANE_COUNT else v)
    return JudgeCounts(values[0], values[1], values[2], values[3])


def _revalidate(handle: int, addrs: list[int]) -> bool:
    """便宜的复验：每个值前面 4 字节的标记还在不在。"""
    buf = ctypes.create_string_buffer(4)
    read = ctypes.c_size_t(0)
    for a in addrs:
        ok = winapi.kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(a - 4), buf, 4, ctypes.byref(read))
        if not ok or read.value != 4 or buf.raw[:4] != _MARKER:
            return False
    return True
