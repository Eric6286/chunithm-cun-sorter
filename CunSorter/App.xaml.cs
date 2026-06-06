using Microsoft.UI.Xaml;

namespace CunSorter;

/// <summary>
/// Application entry point. Mirrors the Python <c>main()</c>: sets the explicit
/// AppUserModelID (so the taskbar shows our name/icon, not "dotnet"), then
/// creates the single main window. Closing that window hides to tray instead of
/// quitting while the watcher is running (see <see cref="MainWindow"/>).
/// </summary>
public partial class App : Application
{
    public const string AppName = "今天你寸了吗";
    public static Window? MainWindow { get; private set; }

    public App()
    {
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            // Match the Python SetCurrentProcessExplicitAppUserModelID call.
            Native.NativeUtil.SetAppUserModelId("JinTianNiCunLeMa.App");
        }
        catch { /* best effort */ }

        MainWindow = new MainWindow();
        MainWindow.Activate();
    }
}
