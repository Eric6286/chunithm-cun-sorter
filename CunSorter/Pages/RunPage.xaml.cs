using System;
using System.IO;
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
        RefreshStartBat();
        SetWatchState(_main.WatcherRunning, _main.WatcherRunning ? "监视: 运行中" : "监视: 未启动");
        _initializing = false;
    }

    private void RefreshStartBat()
    {
        var bat = _main.Cfg.StartBat;
        var hooked = !string.IsNullOrEmpty(bat) && StartBatService.IsHooked(bat);
        StartBatBox.IsChecked = hooked;
        StartBatLabel.Text = hooked ? bat
            : string.IsNullOrEmpty(bat) ? "" : $"{bat}（未接入）";
    }

    private void Mode_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_initializing) return;
        _main.OnModeChanged(ModeBox.SelectedIndex == 0 ? "realtime" : "on_close");
    }

    private void Start_Click(object sender, RoutedEventArgs e) => _main.ToggleWatch();

    private void Autostart_Click(object sender, RoutedEventArgs e) =>
        AutostartService.Set(AutostartBox.IsChecked == true);

    private async void StartBat_Click(object sender, RoutedEventArgs e)
    {
        if (StartBatBox.IsChecked == true)
        {
            // Reuse the remembered path when it still exists; otherwise ask.
            var bat = _main.Cfg.StartBat;
            if (string.IsNullOrEmpty(bat) || !File.Exists(bat))
            {
                bat = await _main.PickFileAsync(".bat", ".cmd");
                if (string.IsNullOrEmpty(bat)) { RefreshStartBat(); return; }
            }
            try
            {
                StartBatService.Hook(bat);
                _main.Cfg.StartBat = bat;
                ConfigService.Save(_main.Cfg);
                _main.ShowInfo("已接入", $"已在 {Path.GetFileName(bat)} 中加入自启动行（原文件备份为 .cun-backup）",
                    InfoBarSeverity.Success);
            }
            catch (Exception ex)
            {
                _main.ShowInfo("接入失败", ex.Message, InfoBarSeverity.Error);
            }
        }
        else
        {
            try
            {
                if (!string.IsNullOrEmpty(_main.Cfg.StartBat))
                    StartBatService.Unhook(_main.Cfg.StartBat);
            }
            catch (Exception ex)
            {
                _main.ShowInfo("移除失败", ex.Message, InfoBarSeverity.Error);
            }
        }
        RefreshStartBat();
    }

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
