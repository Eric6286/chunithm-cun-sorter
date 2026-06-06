using System.Collections.Generic;
using CunSorter.Models;
using CunSorter.Services;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace CunSorter.Pages;

/// <summary>
/// Rule-settings page: one card per category with an on/off switch and the
/// editable numeric bounds. Mirrors <c>ConfigInterface</c> in cun_gui.py.
/// </summary>
public sealed partial class ConfigPage : Page
{
    private sealed class RowRefs
    {
        public ToggleSwitch Switch = null!;
        public NumberBox? Lo;
        public NumberBox? MHi;
        public NumberBox? AHi;
        public ComboBox? Rank;
    }

    private readonly MainWindow _main;
    private readonly Dictionary<string, RowRefs> _rows = new();

    public ConfigPage(MainWindow main)
    {
        _main = main;
        InitializeComponent();
        foreach (var cat in _main.Cfg.Categories)
            Rows.Children.Add(BuildCard(cat));
    }

    private static NumberBox Num(double value, double max, double width)
    {
        return new NumberBox
        {
            Value = value,
            Minimum = 0,
            Maximum = max,
            SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Hidden,
            Width = width,
            VerticalAlignment = VerticalAlignment.Center,
        };
    }

    private static TextBlock Label(string text) => new()
    {
        Text = text,
        VerticalAlignment = VerticalAlignment.Center,
    };

    private List<string> Ranks() => ConfigService.Ranks(_main.Cfg);

    private Border BuildCard(Category cat)
    {
        var grid = new Grid { ColumnSpacing = 14 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var sw = new ToggleSwitch { IsOn = cat.Enabled, OnContent = "", OffContent = "", MinWidth = 0 };
        Grid.SetColumn(sw, 0);
        grid.Children.Add(sw);

        var titleCol = new StackPanel { Spacing = 2, VerticalAlignment = VerticalAlignment.Center };
        titleCol.Children.Add(new TextBlock
        {
            Text = string.IsNullOrEmpty(cat.Label) ? cat.Key : cat.Label,
            Style = (Style)Application.Current.Resources["BodyStrongTextBlockStyle"],
        });
        titleCol.Children.Add(new TextBlock
        {
            Text = "→ " + cat.Folder,
            Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"],
            Opacity = 0.75,
        });
        Grid.SetColumn(titleCol, 1);
        grid.Children.Add(titleCol);

        var ctrls = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
        };
        Grid.SetColumn(ctrls, 2);
        grid.Children.Add(ctrls);

        var refs = new RowRefs { Switch = sw };
        switch (cat.Kind)
        {
            case "score":
                var lo = Num(cat.Lo ?? 0, cat.Hi ?? 1010000, 132);
                ctrls.Children.Add(Label("得分"));
                ctrls.Children.Add(lo);
                ctrls.Children.Add(Label($"~ {cat.Hi ?? 0:N0}"));
                refs.Lo = lo;
                break;
            case "ajcun":
                var mhi = Num(cat.MHi ?? 4, 100, 72);
                ctrls.Children.Add(Label("0 < MISS ≤"));
                ctrls.Children.Add(mhi);
                refs.MHi = mhi;
                break;
            case "am":
                var ahi = Num(cat.AHi ?? 4, 100, 72);
                var mhi2 = Num(cat.MHi ?? 4, 100, 72);
                var rank = new ComboBox { Width = 120, VerticalAlignment = VerticalAlignment.Center };
                foreach (var r in Ranks()) rank.Items.Add(r);
                rank.SelectedItem = Ranks().Contains(cat.MinRank ?? "SSS") ? (cat.MinRank ?? "SSS") : null;
                ctrls.Children.Add(Label("ATTACK ≤"));
                ctrls.Children.Add(ahi);
                ctrls.Children.Add(Label("MISS ≤"));
                ctrls.Children.Add(mhi2);
                ctrls.Children.Add(Label("且评级 ≥"));
                ctrls.Children.Add(rank);
                refs.AHi = ahi; refs.MHi = mhi2; refs.Rank = rank;
                break;
            // "aj" and "fc" have only the on/off switch.
        }
        _rows[cat.Key] = refs;

        return new Border
        {
            Style = (Style)Resources["RowCard"],
            Child = grid,
        };
    }

    private static int IVal(NumberBox? nb, int fallback)
    {
        if (nb == null || double.IsNaN(nb.Value)) return fallback;
        return (int)System.Math.Round(nb.Value);
    }

    /// <summary>Read the current UI state back into the config object.</summary>
    public void ReadInto(CunConfig cfg)
    {
        foreach (var cat in cfg.Categories)
        {
            if (!_rows.TryGetValue(cat.Key, out var r)) continue;
            cat.Enabled = r.Switch.IsOn;
            switch (cat.Kind)
            {
                case "score":
                    cat.Lo = IVal(r.Lo, cat.Lo ?? 0);   // upper (hi) stays fixed
                    break;
                case "ajcun":
                    cat.MHi = IVal(r.MHi, cat.MHi ?? 4);
                    break;
                case "am":
                    cat.AHi = IVal(r.AHi, cat.AHi ?? 4);
                    cat.MHi = IVal(r.MHi, cat.MHi ?? 4);
                    cat.MinRank = r.Rank?.SelectedItem as string ?? cat.MinRank;
                    cat.ScoreMin = null;   // am uses min_rank; clear legacy keys
                    break;
            }
        }
    }

    private void Save_Click(object sender, RoutedEventArgs e) => _main.SaveConfigFromUi();
    private void Rescan_Click(object sender, RoutedEventArgs e) => _main.ApplyAndRescan();
    private void Open_Click(object sender, RoutedEventArgs e) => _main.OpenOutput();
}
