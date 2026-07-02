using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using CunSorter.Native;

namespace CunSorter.Services;

/// <summary>One tick of judgment counters read from game memory.</summary>
public readonly record struct JudgeCounts(int Critical, int Justice, int Attack, int Miss)
{
    public int Total => Critical + Justice + Attack + Miss;

    /// <summary>
    /// CHUNITHM score is purely judgment-weighted (no combo bonus): each note is
    /// worth 1,000,000/total, JC pays 101%, JUSTICE 100%, ATTACK 50%, MISS 0.
    /// All-JC = 1,010,000. May differ from the in-game display by ±1 from rounding.
    /// </summary>
    public int Score => Total == 0
        ? 0
        : (int)Math.Round(1_000_000.0 * (1.01 * Critical + Justice + 0.5 * Attack) / Total);
}

/// <summary>
/// Reads the four judgment counters (JC / JUSTICE / ATTACK / MISS) directly from
/// the running game process, ported from Chuni2Api's signature scan: find the
/// <c>NUM_xxx\0</c> field-name strings in committed heap regions (≥0x50000000),
/// counter value = u16 at signature+0x238 (marker 03 00 00 00 at +0x234).
/// The counter block is freed when a song ends, so a failed read after a PLAYING
/// phase doubles as the settlement signal (an in-place reset to all zero is
/// treated the same way). Read-only: never writes game memory.
/// </summary>
public sealed class JudgeMemoryService
{
    private const int ValueOffset = 0x238;
    private const ulong ScanMinAddr = 0x5000_0000;
    private const ulong ScanMaxAddr = 0xFFFF_0000;      // 32-bit target: stay below 4 GB
    private const int MaxHits = 3;
    private const int PollMs = 50;                      // 20 Hz, same as Chuni2Api
    private const int RescanDelayMs = 1500;
    private const int WaitGameMs = 2000;
    private const int MinNotesForSettle = 10;           // ignore aborted/garbage runs

    private static readonly (string Key, byte[] Sig)[] Sigs =
    {
        ("jctirical", Bytes("NUM_jctirical")),
        ("ctirical",  Bytes("NUM_ctirical")),
        ("attack",    Bytes("NUM_attack")),
        ("miss",      Bytes("NUM_miss")),
    };
    private static readonly byte[] Marker = { 0x03, 0x00, 0x00, 0x00 };

    private static byte[] Bytes(string s)
    {
        var raw = System.Text.Encoding.ASCII.GetBytes(s);
        var b = new byte[raw.Length + 1];               // include trailing \0
        raw.CopyTo(b, 0);
        return b;
    }

    private readonly Func<string> _getProcessName;
    private readonly Action<string> _onStatus;
    private readonly Action<JudgeCounts, JudgeCounts> _onDelta;   // (prev, cur) while playing
    private readonly Action<JudgeCounts> _onSongEnd;              // final counters of a song

    private CancellationTokenSource? _cts;
    private Task? _task;

    public JudgeMemoryService(Func<string> getProcessName, Action<string> onStatus,
        Action<JudgeCounts, JudgeCounts> onDelta, Action<JudgeCounts> onSongEnd)
    {
        _getProcessName = getProcessName;
        _onStatus = onStatus;
        _onDelta = onDelta;
        _onSongEnd = onSongEnd;
    }

    public bool IsRunning => _task is { IsCompleted: false };

    public void Start()
    {
        if (IsRunning) return;
        _cts = new CancellationTokenSource();
        var token = _cts.Token;
        _task = Task.Factory.StartNew(() => Run(token), token,
            TaskCreationOptions.LongRunning, TaskScheduler.Default);
    }

    public void Stop() => _cts?.Cancel();

    private void Status(string s)
    {
        try { _onStatus(s); } catch { /* ignore */ }
    }

    // ----------------------------- main loop ----------------------------------
    private void Run(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            var name = _getProcessName();
            if (string.IsNullOrWhiteSpace(name)) name = "chusanApp.exe";
            if (!NativeUtil.IsProcessRunning(name))
            {
                Status("等待游戏进程…");
                if (token.WaitHandle.WaitOne(WaitGameMs)) return;
                continue;
            }

            var pid = PidOf(name);
            if (pid == 0) continue;
            var handle = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, false, pid);
            if (handle == IntPtr.Zero)
            {
                Status("无法打开游戏进程（权限不足？）");
                if (token.WaitHandle.WaitOne(5000)) return;
                continue;
            }
            try { ReadLoop(handle, pid, token); }
            finally { CloseHandle(handle); }
        }
    }

    /// <summary>Scan → poll cycle for one process lifetime; returns when the
    /// process exits or the service is stopped.</summary>
    private void ReadLoop(IntPtr handle, int pid, CancellationToken token)
    {
        Status("已连接游戏，扫描判定地址…");
        ulong[]? addrs = null;

        while (!token.IsCancellationRequested)
        {
            // (Re)locate the counter block. Try to revalidate the previous
            // addresses first — the block can survive between songs — before
            // paying for a full region scan.
            if (addrs == null || !Revalidate(handle, addrs))
            {
                addrs = FindFields(handle, token);
                if (addrs == null)
                {
                    if (!IsProcessAlive(pid)) { Status("游戏已退出"); return; }
                    Status("未找到判定数据（菜单/加载中），稍后重扫…");
                    if (token.WaitHandle.WaitOne(RescanDelayMs)) return;
                    continue;
                }
                Status("判定地址已锁定，实时读取中");
            }

            // Poll at 20 Hz until reads fail (block freed = song over) or stop.
            JudgeCounts prev = default;
            bool hasPrev = false;
            JudgeCounts lastPlaying = default;
            bool played = false;

            while (!token.IsCancellationRequested)
            {
                var cur = ReadCounts(handle, addrs);
                if (cur == null)
                {
                    // Memory freed: settle the song we just watched, then rescan.
                    SettleIfPlayed(ref played, lastPlaying);
                    addrs = null;
                    if (!IsProcessAlive(pid)) { Status("游戏已退出"); return; }
                    break;
                }

                var c = cur.Value;
                if (c.Total == 0)
                {
                    // In-place reset to zero: menu, or the boundary after a song
                    // when the block is reused instead of freed.
                    SettleIfPlayed(ref played, lastPlaying);
                    hasPrev = false;
                }
                else
                {
                    if (hasPrev && (c.Miss > prev.Miss || c.Attack > prev.Attack ||
                                    c.Critical > prev.Critical || c.Justice > prev.Justice))
                    {
                        try { _onDelta(prev, c); } catch { /* ignore */ }
                    }
                    prev = c;
                    hasPrev = true;
                    lastPlaying = c;
                    played = true;
                }

                if (token.WaitHandle.WaitOne(PollMs)) return;
            }
        }
    }

    private void SettleIfPlayed(ref bool played, JudgeCounts last)
    {
        if (!played) return;
        played = false;
        if (last.Total < MinNotesForSettle) return;
        try { _onSongEnd(last); } catch { /* ignore */ }
    }

    // ----------------------------- reading ------------------------------------
    private static JudgeCounts? ReadCounts(IntPtr handle, ulong[] addrs)
    {
        Span<int> v = stackalloc int[4];
        var buf = new byte[2];
        for (int i = 0; i < 4; i++)
        {
            if (!ReadProcessMemory(handle, (IntPtr)addrs[i], buf, 2, out var n) || n != (nuint)2)
                return null;
            int u = buf[0] | (buf[1] << 8);
            v[i] = u > 30000 ? 0 : u;                   // garbage guard, as upstream
        }
        return new JudgeCounts(v[0], v[1], v[2], v[3]);
    }

    /// <summary>Cheap check that previously found addresses still hold the
    /// counter block (marker dword intact right before each value).</summary>
    private static bool Revalidate(IntPtr handle, ulong[] addrs)
    {
        var buf = new byte[4];
        foreach (var a in addrs)
        {
            if (!ReadProcessMemory(handle, (IntPtr)(a - 4), buf, 4, out var n) || n != (nuint)4)
                return false;
            if (!buf.AsSpan().SequenceEqual(Marker)) return false;
        }
        return true;
    }

    // ----------------------------- signature scan -----------------------------
    /// <summary>Enumerate committed readable regions ≥0x50000000 and search each
    /// for the four <c>NUM_xxx\0</c> signatures (marker-validated). Returns the
    /// four value addresses (highest instance wins, mirroring Chuni2Api) or null.</summary>
    private static ulong[]? FindFields(IntPtr handle, CancellationToken token)
    {
        var hits = new List<ulong>[4];
        for (int i = 0; i < 4; i++) hits[i] = new List<ulong>();
        // The marker sits at sig+0x234..0x238; keep that much overlap between
        // chunks so a match straddling a chunk boundary is still validated.
        int tail = ValueOffset + Sigs.Max(s => s.Sig.Length);

        var chunk = new byte[1 << 20];                  // 1 MB read window

        ulong addr = 0;
        while (addr < ScanMaxAddr && !token.IsCancellationRequested)
        {
            if (VirtualQueryEx(handle, (IntPtr)addr, out var mbi, (nuint)Marshal.SizeOf<MEMORY_BASIC_INFORMATION>()) == 0)
            {
                addr += 0x1000;
                continue;
            }
            ulong base_ = (ulong)mbi.BaseAddress;
            ulong rsize = (ulong)mbi.RegionSize;
            ulong next = rsize > 0 ? base_ + rsize : addr + 0x1000;

            bool readable = mbi.State == MEM_COMMIT && rsize > 0 &&
                            (mbi.Protect & PAGE_GUARD) == 0 &&
                            ReadableProt.Contains(mbi.Protect & 0xFF);
            if (readable && base_ >= ScanMinAddr)
            {
                if (hits.All(h => h.Count >= MaxHits)) break;
                ScanRegion(handle, base_, rsize, chunk, tail, hits);
            }
            addr = next > addr ? next : addr + 0x1000;
        }

        var found = new ulong[4];
        for (int i = 0; i < 4; i++)
        {
            if (hits[i].Count == 0) return null;
            found[i] = hits[i].Max();                   // heap (runtime) instance = highest address
        }
        return found;
    }

    private static void ScanRegion(IntPtr handle, ulong base_, ulong size,
        byte[] chunk, int tail, List<ulong>[] hits)
    {
        ulong offset = 0;
        while (offset < size)
        {
            int want = (int)Math.Min((ulong)chunk.Length, size - offset);
            if (!ReadProcessMemory(handle, (IntPtr)(base_ + offset), chunk, (nuint)want, out var got) || got == 0)
                return;                                 // region vanished mid-scan
            var data = chunk.AsSpan(0, (int)got);
            for (int si = 0; si < Sigs.Length; si++)
            {
                if (hits[si].Count >= MaxHits) continue;
                var sig = Sigs[si].Sig;
                int from = 0;
                while (hits[si].Count < MaxHits)
                {
                    int pos = data[from..].IndexOf(sig);
                    if (pos < 0) break;
                    pos += from;
                    int markerOff = pos + ValueOffset - 4;
                    if (markerOff + 4 <= data.Length &&
                        data.Slice(markerOff, 4).SequenceEqual(Marker))
                    {
                        var v = base_ + offset + (ulong)pos + ValueOffset;
                        if (!hits[si].Contains(v)) hits[si].Add(v);   // chunk overlap can re-find one
                    }
                    from = pos + 1;
                }
            }
            if ((ulong)got < (ulong)want) return;
            if (offset + got >= size) return;
            if (got <= (nuint)tail) return;             // tiny region tail: nothing left to see
            offset += got - (ulong)tail;                // step back so boundary matches re-scan
        }
    }

    // ----------------------------- win32 --------------------------------------
    private static int PidOf(string name)
    {
        var bare = name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? name[..^4] : name;
        try
        {
            var ps = System.Diagnostics.Process.GetProcessesByName(bare);
            return ps.Length > 0 ? ps[0].Id : 0;
        }
        catch { return 0; }
    }

    private static bool IsProcessAlive(int pid)
    {
        try { return !System.Diagnostics.Process.GetProcessById(pid).HasExited; }
        catch { return false; }
    }

    private const uint PROCESS_VM_READ = 0x0010;
    private const uint PROCESS_QUERY_INFORMATION = 0x0400;
    private const uint MEM_COMMIT = 0x1000;
    private const uint PAGE_GUARD = 0x100;
    private static readonly HashSet<uint> ReadableProt = new() { 0x02, 0x04, 0x20, 0x40 };

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, int pid);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr baseAddr,
        byte[] buffer, nuint size, out nuint bytesRead);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern nuint VirtualQueryEx(IntPtr hProcess, IntPtr addr,
        out MEMORY_BASIC_INFORMATION mbi, nuint length);
}
