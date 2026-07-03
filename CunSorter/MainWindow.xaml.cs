using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using CunSorter.Models;
using CunSorter.Pages;
using CunSorter.Services;
using Microsoft.UI;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media.Animation;

namespace CunSorter;

/// <summary>
/// Main window: Fluent NavigationView with three pages (config / stats / run),
/// Mica backdrop, a system-tray icon, and the shared services that the pages
/// drive. Closing the window keeps the watcher running in the tray. Mirrors the
/// PySide6 <c>MainWindow</c> in cun_gui.py.
/// </summary>
public sealed partial class MainWindow : Window
{
    public CunConfig Cfg { get; private set; }
    public OcrService Ocr { get; } = new();

    public ConfigPage ConfigPage { get; }
    public StatsPage StatsPage { get; }
    public RunPage RunPage { get; }

    private readonly AppWindow _appWindow;
    private readonly DispatcherQueueTimer _gameTimer;
    private WatcherService? _watcher;
    private JudgeMemoryService? _judge;
    private LinkServerService? _link;
    private CaptureService? _capture;

    public MainWindow()
    {
        InitializeComponent();
        // Double-click the tray icon = show, independent of the context menu.
        TrayIcon.DoubleClickCommand = new RelayCommand(ShowNormal);
        Cfg = ConfigService.Load();

        _appWindow = GetAppWindow();
        _appWindow.Title = App.AppName;
        Native.NativeUtil.EnableDarkTitleBar(WinRT.Interop.WindowNative.GetWindowHandle(this));
        _appWindow.Resize(new Windows.Graphics.SizeInt32(1040, 720));
        var ico = Path.Combine(ConfigService.Here, "Assets", "icon.ico");
        if (!File.Exists(ico)) ico = Path.Combine(AppContext.BaseDirectory, "Assets", "icon.ico");
        try { if (File.Exists(ico)) _appWindow.SetIcon(ico); } catch { /* ignore */ }
        _appWindow.Closing += AppWindow_Closing;

        ConfigPage = new ConfigPage(this);
        StatsPage = new StatsPage(this);
        RunPage = new RunPage(this);
        ContentFrame.Content = ConfigPage;

        // Poll game status for the indicator (every 4s, like the Qt timer).
        _gameTimer = DispatcherQueue.CreateTimer();
        _gameTimer.Interval = TimeSpan.FromSeconds(4);
        _gameTimer.Tick += (_, _) => UpdateGameLabel();
        _gameTimer.Start();
        UpdateGameLabel();
        ApplyDgHubLink();
    }

    private AppWindow GetAppWindow()
    {
        var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var id = Win32Interop.GetWindowIdFromWindow(hwnd);
        return AppWindow.GetFromWindowId(id);
    }

    /// <summary>
    /// Show the system folder picker, initialised against this window (required
    /// for unpackaged WinUI 3 apps). Returns the chosen path, or null if cancelled.
    /// </summary>
    public async Task<string?> PickFolderAsync()
    {
        // The unpackaged WinUI 3 folder picker can throw (InitializeWithWindow /
        // PickSingleFolderAsync HRESULTs). Callers are async void, so an unhandled
        // throw would terminate the app — swallow to a friendly message + null.
        try
        {
            var picker = new Windows.Storage.Pickers.FolderPicker();
            picker.FileTypeFilter.Add("*");
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            var folder = await picker.PickSingleFolderAsync();
            return folder?.Path;
        }
        catch (Exception e)
        {
            ShowInfo("选择目录失败", e.Message, InfoBarSeverity.Error);
            return null;
        }
    }

    /// <summary>Show the system file picker filtered to the given extensions
    /// (e.g. ".bat"). Returns the chosen path, or null if cancelled.</summary>
    public async Task<string?> PickFileAsync(params string[] extensions)
    {
        try
        {
            var picker = new Windows.Storage.Pickers.FileOpenPicker();
            foreach (var e in extensions) picker.FileTypeFilter.Add(e);
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            var file = await picker.PickSingleFileAsync();
            return file?.Path;
        }
        catch (Exception e)
        {
            ShowInfo("选择文件失败", e.Message, InfoBarSeverity.Error);
            return null;
        }
    }

    /// <summary>start.bat launch (--watch): begin watching right away and drop to
    /// the tray, so the game boot isn't covered by our window.</summary>
    public void EnterWatchMode()
    {
        if (!WatcherRunning) ToggleWatch();
        DispatcherQueue.TryEnqueue(() =>
        {
            _appWindow.Hide();
            try { TrayIcon.ShowNotification(App.AppName, "已随游戏启动，后台监视中。"); }
            catch { /* notifications are best-effort */ }
        });
    }

    private void Nav_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItem as NavigationViewItem)?.Tag as string;
        switch (tag)
        {
            case "config": ShowPage(ConfigPage); break;
            case "stats": ShowPage(StatsPage); StatsPage.Refresh(); break;
            case "run": ShowPage(RunPage); break;
        }
    }

    /// <summary>Swap the frame content with a brief fade + rise so page changes
    /// don't snap. Opacity and TranslateTransform.Y both animate on the
    /// composition thread, so this stays smooth without dependent animations.</summary>
    private void ShowPage(UIElement page)
    {
        if (ReferenceEquals(ContentFrame.Content, page)) return;
        ContentFrame.Content = page;

        var sb = new Storyboard();
        var fade = new DoubleAnimation
        {
            From = 0, To = 1,
            Duration = new Duration(TimeSpan.FromMilliseconds(200)),
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut },
        };
        Storyboard.SetTarget(fade, ContentFrame);
        Storyboard.SetTargetProperty(fade, "Opacity");
        sb.Children.Add(fade);

        var slide = new DoubleAnimation
        {
            From = 16, To = 0,
            Duration = new Duration(TimeSpan.FromMilliseconds(260)),
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut },
        };
        Storyboard.SetTarget(slide, ContentTranslate);
        Storyboard.SetTargetProperty(slide, "Y");
        sb.Children.Add(slide);

        sb.Begin();
    }

    // ----------------------------- tray --------------------------------------
    private sealed class RelayCommand : System.Windows.Input.ICommand
    {
        private readonly Action _run;
        public RelayCommand(Action run) => _run = run;
        public event EventHandler? CanExecuteChanged { add { } remove { } }
        public bool CanExecute(object? p) => true;
        public void Execute(object? p) => _run();
    }

    private void Tray_Show(object sender, RoutedEventArgs e) => ShowNormal();

    private void ShowNormal()
    {
        _appWindow.Show();
        Activate();
    }

    private void Tray_Quit(object sender, RoutedEventArgs e) => Quit();

    private void Quit()
    {
        _watcher?.Stop();
        _judge?.Stop();
        _link?.Stop();
        try { TrayIcon.Dispose(); } catch { /* ignore */ }
        Application.Current.Exit();
    }

    private void AppWindow_Closing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (_watcher is { IsRunning: true })
        {
            args.Cancel = true;
            _appWindow.Hide();
            try { TrayIcon.ShowNotification(App.AppName, "已最小化到托盘，继续后台监视。"); }
            catch { /* notifications are best-effort */ }
        }
        else
        {
            Quit();
        }
    }

    // ----------------------------- info bar ----------------------------------
    private DispatcherQueueTimer? _infoTimer;

    public void ShowInfo(string title, string message, InfoBarSeverity severity, int durationMs = 3000)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            Info.Title = title;
            Info.Message = message;
            Info.Severity = severity;
            InfoHost.Visibility = Visibility.Visible;
            Info.IsOpen = true;
            // One shared auto-close timer, reset on each call. Per-call timers would
            // let an earlier one fire and close a newer toast prematurely.
            if (_infoTimer == null)
            {
                _infoTimer = DispatcherQueue.CreateTimer();
                _infoTimer.IsRepeating = false;
                _infoTimer.Tick += (s, _) => { s.Stop(); Info.IsOpen = false; };
            }
            _infoTimer.Stop();
            _infoTimer.Interval = TimeSpan.FromMilliseconds(durationMs);
            _infoTimer.Start();
        });
    }

    // Collapse the opaque host whenever the bar closes (timer or the user's ✕),
    // so it doesn't leave an empty card occupying the top row.
    private void Info_Closed(InfoBar sender, InfoBarClosedEventArgs args) =>
        InfoHost.Visibility = Visibility.Collapsed;

    // ----------------------------- config ------------------------------------
    public void SaveConfigFromUi()
    {
        ConfigPage.ReadInto(Cfg);
        ConfigService.Save(Cfg);
        ApplyDgHubLink();
        ShowInfo("已保存", "配置已写入 cun_config.json", InfoBarSeverity.Success);
    }

    public void ApplyAndRescan()
    {
        SaveConfigFromUi();
        ShowInfo("正在重新扫描…", "按当前规则重建输出文件夹（不阻塞界面）", InfoBarSeverity.Informational);

        Task.Run(() =>
        {
            ScanResult r;
            try { r = ClassifierService.ScanAll(ConfigService.Load(), Ocr, rebuild: true); }
            catch (Exception e) { r = new ScanResult { Error = e.Message }; }
            DispatcherQueue.TryEnqueue(() => OnScanDone(r));
        });
    }

    private void OnScanDone(ScanResult r)
    {
        StatsPage.Refresh();
        if (r.Error != null)
            ShowInfo("扫描出错", r.Error, InfoBarSeverity.Error, 6000);
        else
            ShowInfo("扫描完成", $"寸={r.Cun}  AJ={r.Aj} (共 {r.Total} 张)", InfoBarSeverity.Success, 4000);
    }

    public void OpenOutput()
    {
        try
        {
            var dir = Cfg.OutputRoot;
            if (string.IsNullOrEmpty(dir))
            {
                ShowInfo("打开失败", "输出目录未配置", InfoBarSeverity.Error);
                return;
            }
            Directory.CreateDirectory(dir);   // no-op if it already exists
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = dir,
                UseShellExecute = true,
            });
        }
        catch (Exception e) { ShowInfo("打开失败", e.Message, InfoBarSeverity.Error); }
    }

    public void OnModeChanged(string mode)
    {
        Cfg.ProcessMode = mode;
        ConfigService.Save(Cfg);
    }

    // ----------------------------- watcher -----------------------------------
    public bool WatcherRunning => _watcher is { IsRunning: true };

    public void ToggleWatch()
    {
        if (_watcher is { IsRunning: true })
        {
            _watcher.Stop();
            _watcher = null;
            RunPage.SetWatchState(false, "监视: 已停止");
        }
        else
        {
            _watcher = new WatcherService(
                getCfg: () => ConfigService.LoadCached(),
                ocr: Ocr,
                onMatch: (f, rec, m) => DispatcherQueue.TryEnqueue(() => OnMatch(f, rec, m)),
                onStatus: s => DispatcherQueue.TryEnqueue(() => OnStatus(s)));
            _watcher.Start();
            RunPage.SetWatchState(true, "监视: 运行中");
        }
    }

    private void OnMatch(string fname, OcrCacheRecord rec, List<Category> matches)
    {
        var keys = string.Join("+", matches.ConvertAll(c => c.Key));
        RunPage.AppendLog($"✓ {fname}  得分={rec.Score} A={rec.Attack} M={rec.Miss}  [{keys}]");
        StatsPage.Refresh();
    }

    private void OnStatus(string msg) => RunPage.SetWatchLabel("监视: " + msg);

    // ----------------------------- memory link -------------------------------
    /// <summary>Start/stop the memory reader plus its two consumers (DGHub event
    /// server, result-screen capture) to match the config. Called at startup and
    /// after every config save, so the toggles take effect immediately. The
    /// DGHub plugin (dghub-plugin/) connects to the server and does the actual
    /// triggering; capture archives the settlement screen with memory-derived
    /// judgment data (no OCR).</summary>
    public void ApplyDgHubLink()
    {
        bool wantLink = Cfg.DgHub.Enabled;
        bool wantCapture = Cfg.Capture.Enabled;

        if (wantLink && _link is not { IsRunning: true })
        {
            _link = new LinkServerService(
                onStatus: s => DispatcherQueue.TryEnqueue(() => RunPage.SetLinkLabel("联动: " + s)));
            _link.Start(Cfg.DgHub.Port);
        }
        else if (!wantLink && _link != null)
        {
            _link.Stop(); _link = null;
            RunPage.SetLinkLabel("联动: 未启用");
        }

        _capture = wantCapture
            ? _capture ?? new CaptureService(
                getCfg: () => ConfigService.LoadCached(),
                onCaptured: OnCaptured,
                onStatus: s =>
                {
                    ClassifierService.Log("[CAPTURE] " + s);   // persistent, for diagnosing timing
                    DispatcherQueue.TryEnqueue(() => RunPage.AppendLog("📸 " + s));
                })
            : null;

        bool wantJudge = wantLink || wantCapture;
        if (wantJudge && _judge is not { IsRunning: true })
        {
            _judge = new JudgeMemoryService(
                getProcessName: () => ConfigService.LoadCached().GameProcess,
                onStatus: s => DispatcherQueue.TryEnqueue(() => RunPage.SetJudgeLabel("判定: " + s)),
                onDelta: (_, _) => { },                  // plugin derives realtime deltas itself
                onSongEnd: OnSongEnd,
                onTick: c => { _link?.UpdateCounts(c); TrackFreeze(c); });
            _judge.Start();
        }
        else if (!wantJudge && _judge != null)
        {
            _judge.Stop(); _judge = null;
            RunPage.SetJudgeLabel("判定: 未启用");
        }
    }

    // Result-screen timing (observed live): the settlement screen shows while
    // the counter block is still alive, frozen at the final values; the block is
    // only freed when the player LEAVES the screen. So the settle signal comes
    // too late for a screenshot — instead, counters frozen for a couple of
    // seconds mid-PLAYING is the "result screen is up" trigger. The fingerprint
    // check inside CaptureService rejects false starts (long note gaps), and
    // the settle-time request stays as a backstop (deduped per song).
    private JudgeCounts _tickLast;
    private long _tickChangedAt;

    private void TrackFreeze(JudgeCounts c)
    {
        var now = Environment.TickCount64;
        if (c != _tickLast)
        {
            _tickLast = c;
            _tickChangedAt = now;
            return;
        }
        // Keep requesting for as long as the freeze lasts (not just once): a
        // false start from a mid-song gap runs its 30s loop and times out, and
        // the result screen may only show after that — the retry catches it.
        // RequestCapture itself is cheap to spam: the busy flag rejects while a
        // loop runs, and the per-song dedupe rejects after a success.
        if (c.Total >= 10 && now - _tickChangedAt >= 2500)
        {
            if (ConfigService.LoadCached().Capture.Enabled) _capture?.RequestCapture(c);
        }
    }

    /// <summary>A captured settlement screenshot was saved: record its judgment
    /// data in the OCR cache (keyed by filename, size-validated) so the watcher
    /// or the next scan classifies it without OCR (capture-service thread).</summary>
    private void OnCaptured(string path, JudgeCounts final)
    {
        var fn = Path.GetFileName(path);
        var rec = new OcrCacheRecord
        {
            Score = final.Score,
            Attack = final.Attack,
            Miss = final.Miss,
            Size = TryFileSize(path),
        };
        if (_watcher is { IsRunning: true } w)
        {
            w.SeedCache(fn, rec);
        }
        else
        {
            var cache = ClassifierService.LoadCache();
            cache[fn] = rec;
            ClassifierService.SaveCache(cache);
        }
        ClassifierService.Log($"[CAPTURE] {fn} score={rec.Score} A={rec.Attack} M={rec.Miss} (memory)");
    }

    private static long? TryFileSize(string path)
    {
        try { return new FileInfo(path).Length; } catch { return null; }
    }

    /// <summary>A song finished (memory freed / counters reset): derive the final
    /// score from the judgment counts, run the user's 寸 rules on it and publish
    /// the verdict to the plugin (memory-reader thread).</summary>
    private void OnSongEnd(JudgeCounts final)
    {
        var cfg = ConfigService.LoadCached();
        var score = final.Score;
        var rank = ConfigService.RankOf(score, cfg) ?? "?";
        var matches = ClassifierService.Classify(score, final.Attack, final.Miss, cfg)
            .Where(c => ClassifierService.CunKinds.Contains(c.Kind)).ToList();
        var keys = string.Join("+", matches.Select(c => c.Key));

        _link?.PublishSettle(new
        {
            @event = "settle",
            cun = matches.Count > 0,
            rules = keys,
            score,
            rank,
            critical = final.Critical,
            justice = final.Justice,
            attack = final.Attack,
            miss = final.Miss,
        });
        var summary = $"得分≈{score} {rank} A{final.Attack}M{final.Miss}";
        ClassifierService.Log($"[SETTLE] {summary} [{(matches.Count > 0 ? keys : "未寸")}]");
        DispatcherQueue.TryEnqueue(() =>
            RunPage.AppendLog($"🏁 结算 {summary}  [{(matches.Count > 0 ? keys : "未寸")}]"));

        if (cfg.Capture.Enabled) _capture?.RequestCapture(final);
    }

    private void UpdateGameLabel()
    {
        var running = Native.NativeUtil.IsProcessRunning(Cfg.GameProcess);
        RunPage.SetGameLabel("游戏: " + (running ? "运行中 ●" : "未运行 ○"));
    }
}
