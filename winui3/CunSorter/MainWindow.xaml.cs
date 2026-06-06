using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using CunSorter.Models;
using CunSorter.Pages;
using CunSorter.Services;
using Microsoft.UI;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

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

    public MainWindow()
    {
        InitializeComponent();
        Cfg = ConfigService.Load();

        _appWindow = GetAppWindow();
        _appWindow.Title = App.AppName;
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
    }

    private AppWindow GetAppWindow()
    {
        var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var id = Win32Interop.GetWindowIdFromWindow(hwnd);
        return AppWindow.GetFromWindowId(id);
    }

    private void Nav_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItem as NavigationViewItem)?.Tag as string;
        switch (tag)
        {
            case "config": ContentFrame.Content = ConfigPage; break;
            case "stats": ContentFrame.Content = StatsPage; StatsPage.Refresh(); break;
            case "run": ContentFrame.Content = RunPage; break;
        }
    }

    // ----------------------------- tray --------------------------------------
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
    public void ShowInfo(string title, string message, InfoBarSeverity severity, int durationMs = 3000)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            Info.Title = title;
            Info.Message = message;
            Info.Severity = severity;
            Info.IsOpen = true;
            var t = DispatcherQueue.CreateTimer();
            t.Interval = TimeSpan.FromMilliseconds(durationMs);
            t.IsRepeating = false;
            t.Tick += (s, _) => { Info.IsOpen = false; t.Stop(); };
            t.Start();
        });
    }

    // ----------------------------- config ------------------------------------
    public void SaveConfigFromUi()
    {
        ConfigPage.ReadInto(Cfg);
        ConfigService.Save(Cfg);
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
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = Cfg.OutputRoot,
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
                getCfg: () => ConfigService.Load(),
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

    private void UpdateGameLabel()
    {
        var running = Native.NativeUtil.IsProcessRunning(Cfg.GameProcess);
        RunPage.SetGameLabel("游戏: " + (running ? "运行中 ●" : "未运行 ○"));
    }
}
