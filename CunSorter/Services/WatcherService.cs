using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CunSorter.Models;
using CunSorter.Native;

namespace CunSorter.Services;

/// <summary>
/// Persistent, game-aware watcher. Detects the game by polling the process list
/// (no need to modify start.bat). Only screenshots that appear AFTER it starts
/// are auto-processed; the existing backlog is left to ScanAll. Faithful port of
/// <c>cun_core.Watcher</c>.
/// </summary>
public sealed class WatcherService
{
    private const double PollSec = 2.0;
    private const double SettleSec = 1.0;

    private readonly Func<CunConfig> _getCfg;
    private readonly OcrService _ocr;
    private readonly Action<string, OcrCacheRecord, List<Category>>? _onMatch;
    private readonly Action<string>? _onStatus;

    private readonly object _cacheLock = new();
    private Dictionary<string, OcrCacheRecord> _cache;
    private CancellationTokenSource? _cts;
    private Task? _task;

    public WatcherService(Func<CunConfig> getCfg, OcrService ocr,
        Action<string, OcrCacheRecord, List<Category>>? onMatch = null,
        Action<string>? onStatus = null)
    {
        _getCfg = getCfg;
        _ocr = ocr;
        _onMatch = onMatch;
        _onStatus = onStatus;
        _cache = ClassifierService.LoadCache();
    }

    public bool IsRunning => _task is { IsCompleted: false };

    public void Start()
    {
        if (IsRunning) return;
        _cts = new CancellationTokenSource();
        _task = Task.Run(() => Run(_cts.Token));
    }

    public void Stop() => _cts?.Cancel();

    private void Status(string msg)
    {
        ClassifierService.Log(msg);
        try { _onStatus?.Invoke(msg); } catch { /* ignore */ }
    }

    private bool Handle(string path, CunConfig cfg)
    {
        OcrCacheRecord rec;
        List<Category> matches;
        lock (_cacheLock)
        {
            rec = ClassifierService.GetOcr(path, cfg, _cache, _ocr);
            matches = ClassifierService.Classify(rec.Score, rec.Attack, rec.Miss, cfg);
            if (matches.Count > 0) ClassifierService.CopyMatches(path, rec, matches, cfg);
            ClassifierService.SaveCache(_cache);
        }
        if (matches.Count > 0)
        {
            var keys = string.Join("+", matches.Select(c => c.Key));
            ClassifierService.Log($"[MATCH] {Path.GetFileName(path)} score={rec.Score} A={rec.Attack} M={rec.Miss} -> {keys}");
            try { _onMatch?.Invoke(Path.GetFileName(path), rec, matches); } catch { /* ignore */ }
        }
        return matches.Count > 0;
    }

    private static bool Settled(string sdir, string f, DateTime now)
    {
        try { return (now - File.GetLastWriteTimeUtc(Path.Combine(sdir, f))).TotalSeconds >= SettleSec; }
        catch { return false; }
    }

    private void Run(CancellationToken token)
    {
        NativeUtil.SetIdlePriority();
        var cfg = _getCfg();
        var sdir = cfg.ScreenshotsDir;
        var baseline = new HashSet<string>(ClassifierService.ListPngs(sdir));
        Status($"watcher started | mode={cfg.ProcessMode} | watching {sdir} ({baseline.Count} existing ignored)");

        var seen = new HashSet<string>();
        var queue = new List<string>();
        bool gamePrev = false;
        var lastGame = DateTime.MinValue;
        DateTime? flushAt = null;

        while (!token.IsCancellationRequested)
        {
            cfg = _getCfg();
            var mode = cfg.ProcessMode;
            var game = string.IsNullOrEmpty(cfg.GameProcess) ? "chusanApp.exe" : cfg.GameProcess;
            var now = DateTime.UtcNow;

            var current = ClassifierService.ListPngs(sdir);
            var ready = current.Where(f => !baseline.Contains(f) && !seen.Contains(f) && Settled(sdir, f, now))
                               .OrderBy(f => f, StringComparer.Ordinal);
            foreach (var f in ready)
            {
                seen.Add(f);
                if (mode == "on_close") queue.Add(f);
                else Handle(Path.Combine(sdir, f), cfg);
            }

            if ((now - lastGame).TotalSeconds >= cfg.GamePollSec)
            {
                lastGame = now;
                var running = NativeUtil.IsProcessRunning(game);
                if (running != gamePrev)
                {
                    gamePrev = running;
                    Status("game " + (running ? "running" : "closed"));
                    if (!running && mode == "on_close" && queue.Count > 0)
                        flushAt = now.AddSeconds(cfg.GameExitGraceSec);
                }
            }

            if (flushAt is not null && now >= flushAt)
            {
                flushAt = null;
                // final sweep: include anything that appeared since
                var extra = ClassifierService.ListPngs(sdir)
                    .Where(f => !baseline.Contains(f) && !seen.Contains(f));
                foreach (var f in new SortedSet<string>(queue.Concat(extra), StringComparer.Ordinal))
                {
                    seen.Add(f);
                    Handle(Path.Combine(sdir, f), cfg);
                }
                Status($"on_close batch processed ({queue.Count})");
                queue.Clear();
            }

            token.WaitHandle.WaitOne(TimeSpan.FromSeconds(PollSec));
        }
        Status("watcher stopped");
    }
}
