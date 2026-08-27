# -*- coding: utf-8 -*-
"""判定数换算得分、配置序列化、结算画面识别。"""

from __future__ import annotations

from core import capture
from core.models import CunConfig, JudgeCounts, OcrRecord


# ----------------------------- 得分换算 -------------------------------------
def test_all_justice_is_a_perfect_score():
    assert JudgeCounts(critical=1000, justice=0, attack=0, miss=0).score == 1_010_000


def test_the_weights_are_101_100_50_0():
    """1000 物量下，各判定各占一份的权重。"""
    assert JudgeCounts(critical=0, justice=1000).score == 1_000_000
    assert JudgeCounts(attack=1000).score == 500_000
    assert JudgeCounts(miss=1000).score == 0


def test_an_empty_chart_scores_zero_instead_of_dividing_by_zero():
    assert JudgeCounts().score == 0
    assert JudgeCounts().total == 0


def test_one_justice_out_of_a_thousand_costs_ten_points():
    full = JudgeCounts(critical=1000).score
    one_off = JudgeCounts(critical=999, justice=1).score
    assert full - one_off == 10


def test_the_score_truncates_instead_of_rounding():
    """游戏显示的是截断值。

    在 150 张真实结算截图上，用顶栏的判定数按公式反算，截断值 149 次与画面上
    的得分完全一致；四舍五入会高 1 分。v1.x 用的是四舍五入，所以联动那条路
    换算的分数系统性偏高，在评级边界上会改判。
    """
    # 2 JC + 1 JUSTICE：精确值 1,006,666.67，四舍五入会给 1,006,667
    assert JudgeCounts(critical=2, justice=1).score == 1_006_666


def test_an_all_justice_run_is_exactly_full_marks_even_at_awkward_note_counts():
    """截断必须走整数运算，否则全 JC 会被算成差 1 分。

    实测有 48 组判定数会踩到：``int(1e6 * (1.01*jc + ...) / total)`` 在
    129 物量全 JC 时给出 1,009,999 而不是 1,010,000。
    """
    assert JudgeCounts(critical=129).score == 1_010_000
    for notes in (2, 4, 16, 32, 65, 129, 1000):
        assert JudgeCounts(critical=notes).score == 1_010_000, notes


# ----------------------------- 配置序列化 -----------------------------------
def test_optional_rule_fields_are_omitted_when_unset():
    """None 的字段不写进 JSON，配置文件才不会长满 null。"""
    from core.models import Category
    d = Category(key="AJ寸", kind="ajcun", m_hi=4).to_dict()
    assert "m_hi" in d
    assert "lo" not in d and "min_rank" not in d
    assert "custom" not in d                      # False 也不写


def test_a_config_survives_a_dict_round_trip():
    cfg = CunConfig()
    cfg.capture.delay_s = 3.0
    cfg.boxes["top_line1"] = [1, 2, 3, 4]
    back = CunConfig.from_dict(cfg.to_dict())
    assert back.capture.delay_s == 3.0
    assert back.boxes["top_line1"] == [1, 2, 3, 4]
    assert back.rank_thresholds == cfg.rank_thresholds


def test_garbage_values_fall_back_to_defaults():
    cfg = CunConfig.from_dict({"game_poll_sec": "不是数字", "dghub": {"port": None},
                               "expected_size": "坏的", "organize": 42})
    assert cfg.game_poll_sec == 4.0
    assert cfg.dghub.port == 8890
    assert cfg.expected_size == [1920, 1080]
    assert len(cfg.organize.steps) == 3


def test_an_ocr_record_without_a_size_omits_the_key():
    assert "size" not in OcrRecord(score=1, attack=0, miss=0).to_dict()
    assert OcrRecord(score=1, size=7).to_dict()["size"] == 7


# ----------------------------- 结算画面识别 ---------------------------------
def _frame(width: int = 1920, height: int = 1080,
           fill: tuple[int, int, int] = (0, 0, 0)) -> capture.Frame:
    r, g, b = fill
    return capture.Frame(bytes([b, g, r, 255]) * (width * height), width, height)


def _paint(frame: capture.Frame, x: int, y: int, rgb: tuple[int, int, int]) -> capture.Frame:
    buf = bytearray(frame.buf)
    i = (y * frame.width + x) * 4
    buf[i:i + 3] = bytes([rgb[2], rgb[1], rgb[0]])
    return capture.Frame(bytes(buf), frame.width, frame.height)


def test_a_black_frame_matches_nothing():
    frame = _frame()
    assert capture.signature_score(frame) == 0
    assert not capture.judge_panel_looks_right(frame)
    assert not capture.is_result_screen(frame)


def test_a_frame_with_every_signature_point_scores_full():
    frame = _frame()
    for x, y, r, g, b in capture.SIGNATURE:
        frame = _paint(frame, x, y, (r, g, b))
    assert capture.signature_score(frame) == len(capture.SIGNATURE)


def test_the_chrome_alone_is_not_enough_to_be_a_result_screen():
    """CLEAR 过场和成绩画面共享全部顶部 chrome，只有判定面板能分开它们。

    这一条对着的是实机上真发生过的误截：指纹 17/17 但截到的是 CLEAR。
    """
    frame = _frame()
    for x, y, r, g, b in capture.SIGNATURE:
        frame = _paint(frame, x, y, (r, g, b))
    assert capture.signature_score(frame) >= capture.MATCH_NEED
    assert not capture.is_result_screen(frame)     # 判定面板那块还是黑的


def test_the_judge_panel_is_matched_by_its_mean_colour():
    x1, y1, x2, y2 = capture.JUDGE_PANEL_RECT
    buf = bytearray(bytes([0, 0, 0, 255]) * (1920 * 1080))
    r, g, b = capture.JUDGE_PANEL_RGB
    for y in range(y1, y2):
        for x in range(x1, x2):
            i = (y * 1920 + x) * 4
            buf[i:i + 3] = bytes([b, g, r])
    assert capture.judge_panel_looks_right(capture.Frame(bytes(buf), 1920, 1080))


def test_signature_points_scale_with_the_resolution():
    """4K 截图也要能对上，坐标按比例换算。"""
    frame = _frame(3840, 2160)
    for x, y, r, g, b in capture.SIGNATURE:
        frame = _paint(frame, x * 2, y * 2, (r, g, b))
    assert capture.signature_score(frame) == len(capture.SIGNATURE)
