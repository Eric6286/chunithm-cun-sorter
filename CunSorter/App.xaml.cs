using System;
using System.Linq;
using System.Threading;
using Microsoft.UI.Xaml;

namespace CunSorter;

/// <summary>
/// Application entry point. Mirrors the Python <c>main()</c>: sets the explicit
/// AppUserModelID (so the taskbar shows our name/icon, not "dotnet"), then
/// creates the single main window. Closing that window hides to tray instead of
/// quitting while the watcher is running (see <see cref="MainWindow"/>).
/// With <c>--watch</c> (injected into the game's start.bat) the app starts
/// watching immediately and minimizes to the tray. A named mutex enforces a
/// single instance, so a start.bat launch while cun is already running is a
/// silent no-op instead of a duplicate watcher.
/// </summary>
public partial class App : Application
{
    public const string AppName = "今天你寸了吗";
    public static Window? MainWindow { get; private set; }

    private static Mutex? _singleInstance;   // held for the process lifetime

    public App()
    {
        // GBK (cp936) for start.bat editing — not in the default .NET Core set.
        System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance);
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        _singleInstance = new Mutex(true, "chunithm-cun-sorter-single-instance", out var isFirst);
        if (!isFirst)
        {
            Current.Exit();
            return;
        }

        try
        {
            // Match the Python SetCurrentProcessExplicitAppUserModelID call.
            Native.NativeUtil.SetAppUserModelId("JinTianNiCunLeMa.App");
        }
        catch { /* best effort */ }

        var watchMode = Environment.GetCommandLineArgs().Contains("--watch");
        var window = new MainWindow();
        MainWindow = window;
        window.Activate();
        if (watchMode) window.EnterWatchMode();
    }
}
