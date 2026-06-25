using System;
using System.Collections.Generic;
using System.Linq;
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
        ShotsDirBox.Text = _main.Cfg.ScreenshotsDir;
        OutDirBox.Text = _main.Cfg.OutputRoot;
        foreach (var cat in _main.Cfg.Categories)
            RuleRows.Children.Add(BuildCard(cat));
        BuildOrganizeList();
    }

    private async void BrowseShots_Click(object sender, RoutedEventArgs e)
    {
        var path = await _main.PickFolderAsync();
        if (string.IsNullOrEmpty(path)) return;
        ShotsDirBox.Text = path;
        // First time the user picks an input dir, mirror it to the output dir so
        // sorted folders land alongside the originals (the historical default).
        if (string.IsNullOrEmpty(OutDirBox.Text))
            OutDirBox.Text = path;
    }

    private async void BrowseOut_Click(object sender, RoutedEventArgs e)
    {
        var path = await _main.PickFolderAsync();
        if (string.IsNullOrEmpty(path)) return;
        OutDirBox.Text = path;
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

        var card = new Border
        {
            Style = (Style)Resources["RowCard"],
            Child = grid,
        };

        var del = new Button { Content = new SymbolIcon(Symbol.Delete), VerticalAlignment = VerticalAlignment.Center };
        ToolTipService.SetToolTip(del, "删除此判定规则");
        del.Click += (_, __) => RemoveCustom(cat, card);
        ctrls.Children.Add(del);

        return card;
    }

    private void RemoveCustom(Category cat, FrameworkElement card)
    {
        _main.Cfg.Categories.Remove(cat);
        _rows.Remove(cat.Key);
        RuleRows.Children.Remove(card);
    }

    private string UniqueKey(string label)
    {
        var baseKey = string.IsNullOrWhiteSpace(label) ? "custom" : label.Trim();
        var existing = _main.Cfg.Categories.Select(c => c.Key).ToHashSet();
        var key = baseKey;
        for (int i = 2; existing.Contains(key); i++) key = $"{baseKey}_{i}";
        return key;
    }

    private static StackPanel LabeledRow(string label, FrameworkElement control)
    {
        var sp = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10, VerticalAlignment = VerticalAlignment.Center };
        sp.Children.Add(new TextBlock { Text = label, MinWidth = 84, VerticalAlignment = VerticalAlignment.Center });
        sp.Children.Add(control);
        return sp;
    }

    // 评级判定 second-level presets. The named ranges come from
    // ConfigService.ScorePresets (single source of truth) and the last entry lets
    // the user type a custom range (null bounds).
    private static readonly string[] RankPresetNames =
        ConfigService.ScorePresets.Select(p => p.Name).Append("自定义区间").ToArray();
    private static readonly (int Lo, int Hi)?[] RankPresetVals =
        ConfigService.ScorePresets
            .Select(p => ((int Lo, int Hi)?)(p.Lo, p.Hi))
            .Append(null)
            .ToArray();

    /// <summary>Dialog to define a new 寸 judgment rule: name, a top-level type
    /// (评级判定 / 差点AJ / ATTACK+MISS), the kind-specific bounds, and an output
    /// folder. 评级判定 reveals a second dropdown of rating presets. The rule is
    /// added to the list and persists on the next 保存配置.</summary>
    private async void AddCustom_Click(object sender, RoutedEventArgs e)
    {
        var nameBox = new TextBox { Header = "名称", PlaceholderText = "例如：SSS寸" };

        string[] kindNames = { "评级判定", "AJ寸（A=0，0<MISS≤x）", "ATTACK+MISS（A≤a，M≤m，评级≥）" };
        string[] kindKeys = { "score", "ajcun", "am" };
        var kindBox = new ComboBox { Header = "判定类型", HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var n in kindNames) kindBox.Items.Add(n);
        kindBox.SelectedIndex = 0;

        var presetBox = new ComboBox { Header = "评级档位", HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var n in RankPresetNames) presetBox.Items.Add(n);
        presetBox.SelectedIndex = 0;

        var folderBox = new TextBox { Header = "输出文件夹（留空＝寸/名称）", PlaceholderText = "寸/名称" };

        // Built once; rows are swapped in/out so each control keeps one parent.
        var lo = Num(0, 1010000, 150);
        var hi = Num(1010000, 1010000, 150);
        var mhi = Num(4, 100, 90);
        var ahi = Num(4, 100, 90);
        var rank = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var r in Ranks()) rank.Items.Add(r);
        rank.SelectedItem = Ranks().Contains("SSS") ? "SSS" : null;
        var hiText = new TextBlock { VerticalAlignment = VerticalAlignment.Center };

        var loRow = LabeledRow("得分下限", lo);
        var hiRow = LabeledRow("得分上限", hi);
        var hiFixedRow = LabeledRow("得分上限", hiText);   // shown for presets (hi locked)
        var mhiRow = LabeledRow("MISS 上限", mhi);
        var ahiRow = LabeledRow("ATTACK 上限", ahi);
        var rankRow = LabeledRow("评级 ≥", rank);

        bool IsCustomRange() => presetBox.SelectedIndex == RankPresetNames.Length - 1;

        // Name auto-fills to the current choice and tracks it, until the user
        // types something of their own (then we stop overwriting).
        string lastSuggest = "";
        string? Suggested() => kindKeys[kindBox.SelectedIndex] switch
        {
            "score" => IsCustomRange() ? null : RankPresetNames[presetBox.SelectedIndex],
            "ajcun" => "AJ寸",
            "am" => "AM寸",
            _ => null,
        };
        void SuggestName()
        {
            var s = Suggested();
            if (s != null && (string.IsNullOrWhiteSpace(nameBox.Text) || nameBox.Text == lastSuggest))
            {
                nameBox.Text = s;
                lastSuggest = s;
            }
        }

        // Apply the selected rating preset to the lo/hi controls (lower bound stays
        // editable, upper bound is fixed by the preset).
        void ApplyPreset()
        {
            if (IsCustomRange()) { lo.Maximum = 1010000; return; }
            var pv = RankPresetVals[presetBox.SelectedIndex]!.Value;
            lo.Maximum = pv.Hi;
            lo.Value = pv.Lo;
            hiText.Text = $"{pv.Hi:N0}（固定）";
        }

        var paramPanel = new StackPanel { Spacing = 8 };
        void Rebuild()
        {
            paramPanel.Children.Clear();
            var k = kindKeys[kindBox.SelectedIndex];
            presetBox.Visibility = k == "score" ? Visibility.Visible : Visibility.Collapsed;
            switch (k)
            {
                case "score":
                    paramPanel.Children.Add(loRow);                          // lower bound always editable
                    paramPanel.Children.Add(IsCustomRange() ? hiRow : hiFixedRow);
                    break;
                case "ajcun": paramPanel.Children.Add(mhiRow); break;
                case "am": paramPanel.Children.Add(ahiRow); paramPanel.Children.Add(mhiRow); paramPanel.Children.Add(rankRow); break;
            }
        }
        kindBox.SelectionChanged += (_, __) => { ApplyPreset(); SuggestName(); Rebuild(); };
        presetBox.SelectionChanged += (_, __) => { ApplyPreset(); SuggestName(); Rebuild(); };
        ApplyPreset();
        SuggestName();
        Rebuild();

        var content = new StackPanel { Spacing = 12, Width = 380 };
        content.Children.Add(nameBox);
        content.Children.Add(kindBox);
        content.Children.Add(presetBox);
        content.Children.Add(paramPanel);
        content.Children.Add(folderBox);

        var dlg = new ContentDialog
        {
            Title = "添加判定规则",
            PrimaryButtonText = "添加",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Primary,
            Content = content,
            XamlRoot = XamlRoot,
        };
        // ShowAsync throws if another ContentDialog is already open or XamlRoot is
        // unavailable; in an async void handler that would crash the app, so guard it.
        ContentDialogResult result;
        try { result = await dlg.ShowAsync(); }
        catch (Exception ex) { _main.ShowInfo("打开对话框失败", ex.Message, InfoBarSeverity.Error); return; }
        if (result != ContentDialogResult.Primary) return;

        var label = nameBox.Text.Trim();
        if (string.IsNullOrEmpty(label))
        {
            _main.ShowInfo("未添加", "名称不能为空", InfoBarSeverity.Warning);
            return;
        }
        var kind = kindKeys[kindBox.SelectedIndex];
        var folder = string.IsNullOrWhiteSpace(folderBox.Text) ? $"寸/{label}" : folderBox.Text.Trim();

        var cat = new Category
        {
            Key = UniqueKey(label), Label = label, Kind = kind,
            Enabled = true, Custom = true, Folder = folder,
        };
        switch (kind)
        {
            case "score":
                if (!IsCustomRange())
                { var pv = RankPresetVals[presetBox.SelectedIndex]!.Value; cat.Lo = IVal(lo, pv.Lo); cat.Hi = pv.Hi; }
                else { cat.Lo = IVal(lo, 0); cat.Hi = IVal(hi, 1010000); }
                break;
            case "ajcun": cat.MHi = IVal(mhi, 4); break;
            case "am": cat.AHi = IVal(ahi, 4); cat.MHi = IVal(mhi, 4); cat.MinRank = rank.SelectedItem as string ?? "SSS"; break;
        }

        _main.Cfg.Categories.Add(cat);
        RuleRows.Children.Add(BuildCard(cat));
        _main.ShowInfo("已添加", $"「{label}」已加入判定规则，记得点「保存配置」", InfoBarSeverity.Success);
    }

    // ----------------------------- organize ----------------------------------
    private sealed class OrgRefs
    {
        public string Kind = "";
        public ToggleSwitch Sw = null!;
        public ComboBox? Span;
    }

    private static readonly string[] SpanKeys = { "year", "month", "day" };
    private static readonly string[] SpanNames = { "按年", "按月", "按日" };

    private static string OrgLabel(string kind) => kind switch
    {
        "date" => "根据日期整理",
        "rank" => "根据评级整理",
        "achievement" => "根据达成整理（AJ / FC / 普通）",
        _ => kind,
    };

    private void BuildOrganizeList()
    {
        foreach (var step in _main.Cfg.Organize.Steps)
            OrganizeList.Items.Add(BuildOrganizeItem(step));
    }

    private ListViewItem BuildOrganizeItem(OrganizeStep step)
    {
        var grid = new Grid { ColumnSpacing = 8 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });                        // handle
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });   // label
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });                        // date span
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });                        // up
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });                        // down
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });                        // toggle

        var handle = new FontIcon { Glyph = "", FontSize = 14, Opacity = 0.55, VerticalAlignment = VerticalAlignment.Center };
        Grid.SetColumn(handle, 0);
        grid.Children.Add(handle);

        var label = new TextBlock
        {
            Text = OrgLabel(step.Kind),
            VerticalAlignment = VerticalAlignment.Center,
            Style = (Style)Application.Current.Resources["BodyStrongTextBlockStyle"],
        };
        Grid.SetColumn(label, 1);
        grid.Children.Add(label);

        var refs = new OrgRefs { Kind = step.Kind };
        if (step.Kind == "date")
        {
            var span = new ComboBox { VerticalAlignment = VerticalAlignment.Center, MinWidth = 92 };
            foreach (var n in SpanNames) span.Items.Add(n);
            span.SelectedIndex = Math.Max(0, Array.IndexOf(SpanKeys, step.DateSpan));
            Grid.SetColumn(span, 2);
            grid.Children.Add(span);
            refs.Span = span;
        }

        var sw = new ToggleSwitch { IsOn = step.Enabled, OnContent = "", OffContent = "", MinWidth = 0, VerticalAlignment = VerticalAlignment.Center };
        Grid.SetColumn(sw, 5);
        grid.Children.Add(sw);
        refs.Sw = sw;

        var item = new ListViewItem { Content = grid, Tag = refs };

        // Explicit up/down buttons — precise reordering without the drag press-hold.
        var up = SmallIconButton("", "上移");
        up.Click += (_, __) => MoveOrganizeItem(item, -1);
        Grid.SetColumn(up, 3);
        grid.Children.Add(up);

        var down = SmallIconButton("", "下移");
        down.Click += (_, __) => MoveOrganizeItem(item, +1);
        Grid.SetColumn(down, 4);
        grid.Children.Add(down);

        return item;
    }

    private static Button SmallIconButton(string glyph, string tip)
    {
        var b = new Button
        {
            Content = new FontIcon { Glyph = glyph, FontSize = 12 },
            Padding = new Thickness(9, 4, 9, 4),
            MinWidth = 0,
            VerticalAlignment = VerticalAlignment.Center,
        };
        ToolTipService.SetToolTip(b, tip);
        return b;
    }

    private void MoveOrganizeItem(ListViewItem item, int delta)
    {
        int i = OrganizeList.Items.IndexOf(item);
        if (i < 0) return;
        int j = i + delta;
        if (j < 0 || j >= OrganizeList.Items.Count) return;
        OrganizeList.Items.RemoveAt(i);
        OrganizeList.Items.Insert(j, item);
    }

    private static int IVal(NumberBox? nb, int fallback)
    {
        if (nb == null || double.IsNaN(nb.Value)) return fallback;
        return (int)System.Math.Round(nb.Value);
    }

    /// <summary>Read the current UI state back into the config object.</summary>
    public void ReadInto(CunConfig cfg)
    {
        cfg.ScreenshotsDir = ShotsDirBox.Text.Trim();
        cfg.OutputRoot = OutDirBox.Text.Trim();

        // Organize steps: take the (possibly drag-reordered) list order, enabled
        // state and per-step date span straight off the ListView.
        var steps = new List<OrganizeStep>();
        foreach (var obj in OrganizeList.Items)
        {
            if (obj is not ListViewItem { Tag: OrgRefs r }) continue;
            var s = new OrganizeStep { Kind = r.Kind, Enabled = r.Sw.IsOn };
            if (r.Kind == "date") s.DateSpan = SpanKeys[Math.Max(0, r.Span?.SelectedIndex ?? 1)];
            steps.Add(s);
        }
        if (steps.Count > 0) cfg.Organize.Steps = steps;

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
