# -*- coding: utf-8 -*-
"""主题的验收：对比度、Token 完整性、QSS 里的雷区。

这些断言钉的是**规范里的底线**，不是当前长相。改配色时它们会红，那正是要的：
挑一个好看的橙色很容易，挑一个在十一种承载面上都还读得清的橙色不容易。

对比度按 sRGB 相对亮度算，与离线生成器同一套公式，所以这里通过 = 那边也通过。
"""

from __future__ import annotations

import re
from pathlib import Path

from ui.theme import metrics, qss, tokens

ROOT = Path(__file__).resolve().parent.parent

#: 普通文本的门槛。规范：只有 metric 和 Mobile pageTitle 够得上「大号文本」的
#: 3:1，其余一律 4.5:1。``text.tertiary`` 用于 caption（11px），也走 4.5:1。
AA_TEXT = 4.5
#: 控件边界、状态图形和焦点指示
AA_NON_TEXT = 3.0

MODES = {"light": tokens.LIGHT, "dark": tokens.DARK}
SEMANTIC_FAMILIES = ("success", "warning", "error", "info")


# ----------------------------- 色彩计算 -------------------------------------
def _channel(v: float) -> float:
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (_channel(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    lo, hi = min(a, b), max(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _linear(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(_channel(int(h[i:i + 2], 16)) for i in (0, 2, 4))    # type: ignore[return-value]


def oklch_hue(hex_color: str) -> float:
    """OKLCH 色相，用来验证分类色之间以及与语义色的角距。"""
    import math
    r, g, b = _linear(hex_color)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v > 0 else -((-v) ** (1 / 3)) for v in (l, m, s))
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return math.degrees(math.atan2(bb, a)) % 360.0


def hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


# 色盲模拟，用于分类色的可辨识性
_CB = {
    "protanopia": ((0.1121, 0.8853, -0.0005), (0.1127, 0.8897, -0.0001),
                   (0.0045, 0.0085, 1.0)),
    "deuteranopia": ((0.2920, 0.7054, -0.0003), (0.2934, 0.7089, 0.0),
                     (-0.0209, 0.0272, 0.9968)),
    "tritanopia": ((1.0, 0.1284, -0.1284), (0.0, 0.8654, 0.1346),
                   (-0.0058, 0.6903, 0.3156)),
}


def _simulate(hex_color: str, kind: str) -> tuple[float, float, float]:
    rgb = _linear(hex_color)
    mat = _CB[kind]
    out = []
    for row in mat:
        v = max(0.0, min(1.0, sum(row[i] * rgb[i] for i in range(3))))
        out.append(255.0 * (12.92 * v if v <= 0.0031308
                            else 1.055 * v ** (1 / 2.4) - 0.055))
    return tuple(out)                                    # type: ignore[return-value]


def cb_distance(a: str, b: str, kind: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(_simulate(a, kind), _simulate(b, kind))) ** 0.5


# ----------------------------- Token 完整性 ---------------------------------
def test_light_and_dark_define_exactly_the_same_tokens():
    """少一个键，那个模式下就是 KeyError，或者 QSS 里静默变成空串。"""
    missing_in_dark = sorted(set(tokens.LIGHT) - set(tokens.DARK))
    missing_in_light = sorted(set(tokens.DARK) - set(tokens.LIGHT))
    assert not missing_in_dark, f"Dark 缺少：{missing_in_dark}"
    assert not missing_in_light, f"Light 缺少：{missing_in_light}"


def test_every_token_resolves_to_a_single_concrete_value():
    """规范的「实现前解析门槛」：主题里不许留区间、auto、TBD、按需、适量。"""
    bad = re.compile(r"\d+\s*[–—]\s*\d+|TBD|auto|按需|适量")
    for name in ("tokens.py", "metrics.py"):
        text = (ROOT / "ui" / "theme" / name).read_text(encoding="utf-8")
        # 只看值，不看注释和文档串里对规范的引用
        for mode, table in MODES.items():
            for key, value in table.items():
                assert not bad.search(value), f"{mode}.{key} 不是单值：{value}"
        del text
    for role, spec in metrics.FONT_ROLES.items():
        assert isinstance(spec.size, int) and spec.size > 0, role
        assert isinstance(spec.line_height, int) and spec.line_height > spec.size, role


def test_the_project_records_which_design_system_revision_it_follows():
    """跨项目视觉对比只在 Revision 一致时才成立，所以必须写下来。"""
    assert tokens.DESIGN_SYSTEM_REVISION == "2026.08.31-a11y-baseline"


def test_every_override_of_a_global_default_carries_a_reason():
    """规范要求项目覆盖写出确定值与原因，不能悄悄漂移。"""
    assert tokens.OVERRIDES
    for item, value, reason in tokens.OVERRIDES:
        assert item and value, item
        assert len(reason) > 20, f"{item} 的原因写得太糊：{reason}"


# ----------------------------- 对比度 ---------------------------------------
def _bearing(table: dict[str, str]) -> list[tuple[str, str]]:
    return [(name, table[name]) for name in tokens.TEXT_BEARING_SURFACES]


def test_neutral_text_is_readable_on_every_text_bearing_surface():
    """规范：每个文字 Token 要在**承载面集合**上逐一达标，不是只对 canvas 校一次。

    最容易漏的是 ``fill.control`` 和各种 ``subtle``——它们比 canvas 暗（浅色模式）
    或亮（深色模式），只对 canvas 校验会放过一批实际读不清的组合。
    """
    for mode, table in MODES.items():
        for role in ("text.primary", "text.secondary", "text.tertiary"):
            for surface_name, surface in _bearing(table):
                ratio = contrast(table[role], surface)
                assert ratio >= AA_TEXT, (
                    f"{mode} {role} 在 {surface_name} 上只有 {ratio:.2f}:1，"
                    f"要求 {AA_TEXT}")


def test_accent_and_semantic_text_are_readable_where_they_are_used():
    for mode, table in MODES.items():
        for surface_name, surface in _bearing(table):
            ratio = contrast(table["accent.text"], surface)
            assert ratio >= AA_TEXT, (
                f"{mode} accent.text 在 {surface_name} 上只有 {ratio:.2f}:1")
        for family in SEMANTIC_FAMILIES:
            text = table[f"semantic.{family}.text"]
            own_subtle = table[f"semantic.{family}.subtle"]
            for surface_name, surface in (("canvas", table["canvas"]),
                                          ("surface", table["surface"]),
                                          ("surfaceElevated", table["surfaceElevated"]),
                                          ("fill.control", table["fill.control"]),
                                          (f"{family}.subtle", own_subtle)):
                ratio = contrast(text, surface)
                assert ratio >= AA_TEXT, (
                    f"{mode} {family}.text 在 {surface_name} 上只有 {ratio:.2f}:1")


def test_the_text_on_an_accent_fill_never_flips_between_states():
    """``accent.onAccent`` 在 Default / Hover / Pressed 三态保持同一个值，
    而且三态都达标——交互时文字突然反色是最刺眼的一种抖动。"""
    for mode, table in MODES.items():
        on = table["accent.onAccent"]
        for state in ("accent.primary", "accent.hover", "accent.pressed"):
            ratio = contrast(on, table[state])
            assert ratio >= AA_TEXT, f"{mode} onAccent 在 {state} 上只有 {ratio:.2f}:1"
        for family in SEMANTIC_FAMILIES:
            solid = table[f"semantic.{family}.solid"]
            ratio = contrast(table[f"semantic.{family}.onSolid"], solid)
            assert ratio >= AA_TEXT, f"{mode} {family}.onSolid 只有 {ratio:.2f}:1"


def test_control_edges_and_focus_ring_reach_three_to_one():
    """控件边界、状态图形和焦点指示的门槛。

    ``fill.control`` 与 ``surface`` 只差约 1.1:1，所以按钮和输入框的边缘完全靠
    ``border.default`` 撑着——它要是不够，控件就等于没有边界。
    """
    for mode, table in MODES.items():
        against = ("canvas", "surface", "surfaceElevated", "fill.control")
        for role in ("border.default", "accent.border", "accent.focus"):
            for name in against:
                if role == "accent.border" and name == "surfaceElevated":
                    continue                     # 边界只需对相邻的实际底色成立
                ratio = contrast(table[role], table[name])
                assert ratio >= AA_NON_TEXT, (
                    f"{mode} {role} 在 {name} 上只有 {ratio:.2f}:1")
        for family in SEMANTIC_FAMILIES:
            ratio = contrast(table[f"semantic.{family}.border"], table["canvas"])
            assert ratio >= AA_NON_TEXT, f"{mode} {family}.border 只有 {ratio:.2f}:1"


def test_hover_and_pressed_move_far_enough_to_be_felt():
    """Hover 要看得出来，Pressed 要比 Hover 更明显，而且同方向。

    候选色板里 Pressed 只比 Default 差 0.024 的 L，按下去几乎没反应；
    规范把幅度定成 Hover 0.03 / Pressed 0.045，这条钉住方向和相对大小。
    """
    for mode, table in MODES.items():
        base = luminance(table["accent.primary"])
        hover = luminance(table["accent.hover"])
        pressed = luminance(table["accent.pressed"])
        assert base != hover, f"{mode} hover 和 default 一模一样"
        assert (hover - base) * (pressed - hover) > 0, (
            f"{mode} pressed 相对 hover 换了方向，按压反馈会自相矛盾")
        assert abs(pressed - base) > abs(hover - base), (
            f"{mode} pressed 的幅度没有超过 hover")


# ----------------------------- 数据可视化 -----------------------------------
def test_chart_series_stay_clear_of_semantic_and_brand_hues():
    """分类色是第四套体系，不从品牌色阶切片。

    与 error / success / warning 至少差 20° 是规范要求；品牌色相一并回避是本项目
    的额外约束——否则一条线会被读成「当前选中」而不是「某个类别」。
    """
    reserved = {"error": 25.0, "success": 145.0, "warning": 76.0,
                "brand": tokens.BRAND_HUE}
    for mode, table in MODES.items():
        for i in range(1, tokens.VIZ_CATEGORICAL_COUNT + 1):
            hue = oklch_hue(table[f"viz.categorical.{i}"])
            for name, other in reserved.items():
                gap = hue_gap(hue, other)
                assert gap >= 20.0, (
                    f"{mode} viz.categorical.{i} 的色相离 {name} 只有 {gap:.1f}°")


def test_chart_series_are_visible_and_mutually_distinguishable():
    """数据标记对图表背景至少 3:1；前几个类别在三种色盲模拟下仍要两两可辨。"""
    for mode, table in MODES.items():
        series = [table[f"viz.categorical.{i}"]
                  for i in range(1, tokens.VIZ_CATEGORICAL_COUNT + 1)]
        for i, color in enumerate(series, 1):
            ratio = contrast(color, table["surfaceSunken"])
            assert ratio >= AA_NON_TEXT, (
                f"{mode} viz.categorical.{i} 在图表底上只有 {ratio:.2f}:1")
        for kind in _CB:
            for i in range(len(series)):
                for j in range(i + 1, len(series)):
                    d = cb_distance(series[i], series[j], kind)
                    assert d >= 40.0, (
                        f"{mode} 第 {i + 1} 和第 {j + 1} 条线在 {kind} 下只差 {d:.1f}")


# ----------------------------- 排版 -----------------------------------------
def test_section_titles_outrank_the_rows_they_head():
    """规范点名禁止把组标题做成 caption、secondary 或弱灰文字。

    v2.0 的组标题正是 11px 弱灰，比它下面的选项还弱。
    """
    assert metrics.SECTION_TITLE.size > metrics.BODY.size, (
        f"组标题 {metrics.SECTION_TITLE.size} 不比行标题 {metrics.BODY.size} 大")
    assert metrics.SECTION_TITLE.weight >= metrics.SEMIBOLD, (
        f"组标题字重只有 {metrics.SECTION_TITLE.weight}，要 Semibold")
    assert metrics.SECONDARY.size < metrics.BODY.size, "secondary 不该和正文一样大"
    assert metrics.CAPTION.size < metrics.SECONDARY.size, "caption 不该和 secondary 一样大"


def test_only_genuinely_large_text_may_be_verified_at_three_to_one():
    """WCAG 的大号文本是 ≥24 任意字重，或 ≥18.66 且 Bold(700)。
    Semibold(600) **不**放宽——本项目只有 metric 够得上。"""
    for role in metrics.LARGE_TEXT_ROLES:
        spec = metrics.FONT_ROLES[role]
        assert spec.size >= 24 or (spec.size >= 18.66 and spec.weight >= 700), (
            f"{role} 登记成了大号文本，但 {spec.size}/{spec.weight} 够不上 WCAG 的判定")
    for role, spec in metrics.FONT_ROLES.items():
        if role in metrics.LARGE_TEXT_ROLES:
            continue
        assert not (spec.size >= 24 or (spec.size >= 18.66 and spec.weight >= 700)), (
            f"{role} 其实够得上大号文本，应该登记进 LARGE_TEXT_ROLES")


def test_settings_rows_are_tall_enough_to_hold_their_content():
    assert metrics.ROW_MIN_HEIGHT == 32, "规范给 Desktop 单行设置项的默认最小行高是 32"
    assert metrics.ROW_WITH_SUBLABEL_MIN_HEIGHT == 48, "含一行说明时是 48"
    assert (metrics.PADDING_CONTROL_Y * 2 + metrics.BODY.line_height
            <= metrics.ROW_WITH_SUBLABEL_MIN_HEIGHT), "行高地板装不下一行正文加上下内边距"


# ----------------------------- QSS ------------------------------------------
def _selectors(sheet: str) -> list[str]:
    out: list[str] = []
    for block in sheet.split("{"):
        head = block.rsplit("}", 1)[-1]
        head = re.sub(r"/\*.*?\*/", " ", head, flags=re.S)
        for sel in head.split(","):
            sel = sel.strip()
            if sel:
                out.append(sel)
    return out


def test_the_stylesheet_never_uses_an_unqualified_qwidget_selector():
    """Qt 的类型选择器连子类一起命中：``QWidget { background }`` 会把每个 QLabel
    都刷上底色，在卡片上显示成一条条横杠。

    带祖先限定的 ``QScrollArea#PageScroll > QWidget`` 是安全的，只有**开头**就是
    光秃秃 QWidget 的那种会波及全局。
    """
    for mode, table in MODES.items():
        for mica in (False, True):
            for sel in _selectors(qss.build(table, mica)):
                first = sel.split()[0]
                assert not re.fullmatch(r"QWidget(:[\w-]+)?", first), (
                    f"{mode} mica={mica} 出现了会波及全局的选择器：{sel}")


def test_the_stylesheet_resolves_every_token_it_mentions():
    """拼错键名会直接 KeyError，这里顺带保证成品里没有空值和残留占位。"""
    for table in MODES.values():
        for mica in (False, True):
            sheet = qss.build(table, mica)
            assert "None" not in sheet, "有 Token 解析成了 None"
            assert "{" in sheet and "}" in sheet, "样式表是空的"
            for line in sheet.splitlines():
                if ":" in line and not line.strip().startswith("/*"):
                    value = line.split(":", 1)[1].strip().rstrip(";")
                    assert value != "", f"空值：{line!r}"


def test_focus_is_not_left_to_qss():
    """QSS 不支持 outline / outline-offset（实测被静默忽略）。

    要是有人「顺手」在这里加回 :focus 的边框规则，控件会在获得焦点时跳一下，
    而且和 FocusRing 画的环叠在一起。
    """
    sheet = qss.build(tokens.DARK, False)
    assert "outline-offset" not in sheet, "QSS 不支持 outline-offset，写了也不画"
    assert ":focus" not in sheet, "焦点表现归 FocusRing，QSS 里加 :focus 会让控件跳一下"
