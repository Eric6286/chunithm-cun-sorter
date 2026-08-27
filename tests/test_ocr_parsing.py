# -*- coding: utf-8 -*-
"""OCR 的文本解析与图像预处理（不需要装 Tesseract）。"""

from __future__ import annotations

from PIL import Image

from core.ocr import (TOP_LINE_PAD, _parse_score, _prep_region, _scaled_box,
                      _top_field)


# ----------------------------- 得分解析 -------------------------------------
def test_a_score_is_picked_out_of_the_line():
    assert _parse_score("OMBO: 1016 SCORE: 1,009,297 |") == 1_009_297


def test_stray_spaces_inside_the_number_are_closed_up():
    """OCR 会在千分位后面塞空格：「1,007 ,603」。"""
    assert _parse_score("SCORE : 1,007 ,603") == 1_007_603


def test_numbers_outside_the_plausible_range_are_ignored():
    assert _parse_score("COMBO: 1016") is None            # 位数不够
    assert _parse_score("SCORE: 9,999,999") is None       # 超过满分
    assert _parse_score("") is None


def test_the_largest_plausible_number_wins():
    """MAX COMBO 也可能被读成 6 位数，得分总是更大的那个。"""
    assert _parse_score("MAX COMBO : 100100 SCORE : 1,009,297") == 1_009_297


# ----------------------------- 顶栏字段 -------------------------------------
def test_a_missing_label_means_the_value_is_zero():
    """游戏把值为 0 的项整个隐藏，所以「没这个标签」＝ 0。"""
    line = "JUSTICE CRITICAL : 1729 | JUSTICE: 22 | MISS: 1"
    value, source = _top_field(line.upper(), "ATTACK", line, r"ATTACK\D{0,4}(\d{1,4})")
    assert (value, source) == (0, "zero")


def test_a_present_label_is_read_from_the_top_bar():
    line = "JUSTICE CRITICAL : 1729 | ATTACK: 16 | MISS: 4"
    assert _top_field(line.upper(), "ATTACK", line, r"ATTACK\D{0,4}(\d{1,4})") == (16, "top")


def test_an_unreadable_number_falls_through_to_the_breakdown():
    line = "ATTACK: ??"
    value, source = _top_field(line.upper(), "ATTACK", line, r"ATTACK\D{0,4}(\d{1,4})")
    assert value is None
    assert source == "unread"                    # 调用方据此去查判定明细面板


# ----------------------------- 区域换算 -------------------------------------
def test_boxes_are_scaled_to_the_actual_resolution():
    box = [558, 6, 1345, 40]
    assert _scaled_box(box, 1920, 1080, [1920, 1080]) == (558, 6, 1345, 40)
    assert _scaled_box(box, 3840, 2160, [1920, 1080]) == (1116, 12, 2690, 80)


# ----------------------------- 预处理 ---------------------------------------
def test_the_region_is_upscaled_and_binarised():
    img = Image.new("RGB", (100, 20), (200, 200, 200))
    out = _prep_region(img, (0, 0, 10, 10), 128, True)
    assert out.size == (40, 40)                  # 放大 4 倍
    assert set(out.tobytes()) <= {0, 255}        # 只有黑白两色


def test_padding_adds_a_background_border_only_when_asked():
    """顶栏要留白（数字紧贴右边界会被读错），得分那一行不能加。"""
    img = Image.new("RGB", (100, 20), (200, 200, 200))
    plain = _prep_region(img, (0, 0, 10, 10), 128, True)
    padded = _prep_region(img, (0, 0, 10, 10), 128, True, pad=TOP_LINE_PAD)
    assert padded.size == (plain.width + TOP_LINE_PAD * 2, plain.height + TOP_LINE_PAD * 2)
    assert padded.getpixel((0, 0)) == 0          # 顶栏模式的背景是黑


def test_a_box_outside_the_image_is_clamped():
    img = Image.new("RGB", (50, 50), (0, 0, 0))
    out = _prep_region(img, (-10, -10, 500, 500), 128, True)
    assert out.width > 0 and out.height > 0
