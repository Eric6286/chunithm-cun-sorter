using CunSorter.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace CunSorter.Pages;

/// <summary>
/// Run / watch page: process-mode switch, start/stop watcher, game + watch
/// status, run-at-login toggle, and a recent-hits log. Mirrors
/// <c>RunInterface</c> in cun_gui.py.
/// </summary>
public sealed partial class RunPage : Page
{
    private readonly MainWindow _main;
    private bool _initializing = true;

    public RunPage(MainWindow main)
    {
        _main = main;
        InitializeComponent();
        ModeBox.SelectedIndex = _main.Cfg.ProcessMode == "realtime" ? 0 : 1;
        AutostartBox.IsChecked = AutostartService.IsEnabled();
        SetWatchState(_main.WatcherRunning, _main.WatcherRunning ? "监视: 运行中" : "监视: 未启动");
        _initializing = false;
    }

    private void Mode_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_initializing) return;
        _main.OnModeChanged(ModeBox.SelectedIndex == 0 ? "realtime" : "on_close");
    }

    private void Start_Click(object sender, RoutedEventArgs e) => _main.ToggleWatch();

    private void Autostart_Click(object sender, RoutedEventArgs e) =>
        AutostartService.Set(AutostartBox.IsChecked == true);

    // ----------------------------- callbacks from MainWindow -----------------
    public void SetWatchState(bool running, string label)
    {
        StartText.Text = running ? "停止监视" : "启动监视";
        WatchLabel.Text = label;
    }

    public void SetWatchLabel(string text) => WatchLabel.Text = text;
    public void SetGameLabel(string text) => GameLabel.Text = text;
    public void SetLinkLabel(string text) => LinkLabel.Text = text;
    public void SetJudgeLabel(string text) => JudgeLabel.Text = text;

    public void AppendLog(string line)
    {
        LogBox.Text += (LogBox.Text.Length > 0 ? "\n" : "") + line;
    }
}
