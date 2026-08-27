# -*- coding: utf-8 -*-
"""判定、复制、整理、扫描范围。"""

from __future__ import annotations

from pathlib import Path

from core import classifier
from core.models import Category, OcrRecord, OrganizeStep


def _png(path: Path, size: int = 64) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * size)
    return path


# ----------------------------- 判定 -----------------------------------------
def test_a_score_rule_matches_only_inside_its_range(cfg, sss_rule):
    cfg.categories = [sss_rule]
    assert classifier.classify(1_007_200, 0, 1, cfg) == [sss_rule]
    assert classifier.classify(1_007_500, 0, 1, cfg) == []      # 上界之外
    assert classifier.classify(1_006_999, 0, 1, cfg) == []      # 下界之外


def test_ajcun_needs_zero_attack_and_at_least_one_miss(cfg):
    rule = Category(key="AJ寸", kind="ajcun", enabled=True, folder="寸/AJ寸", m_hi=4)
    cfg.categories = [rule]
    assert classifier.classify(1_009_000, 0, 1, cfg) == [rule]
    assert classifier.classify(1_009_000, 0, 4, cfg) == [rule]
    assert classifier.classify(1_009_000, 0, 5, cfg) == []      # 超过上限
    assert classifier.classify(1_009_000, 0, 0, cfg) == []      # 这是真 AJ，不是寸
    assert classifier.classify(1_009_000, 1, 1, cfg) == []      # 有 ATTACK 就不算


def test_am_requires_a_rank_floor_and_a_nonzero_blemish(cfg):
    rule = Category(key="AM寸", kind="am", enabled=True, folder="寸/AM寸",
                    a_hi=2, m_hi=2, min_rank="SSS")
    cfg.categories = [rule]
    assert classifier.classify(1_008_000, 1, 1, cfg) == [rule]
    assert classifier.classify(1_008_000, 0, 0, cfg) == []      # A+M 必须大于 0
    assert classifier.classify(1_000_000, 1, 1, cfg) == []      # 评级不到 SSS
    assert classifier.classify(1_008_000, 3, 0, cfg) == []      # ATTACK 超上限


def test_a_disabled_rule_never_matches(cfg, sss_rule):
    sss_rule.enabled = False
    cfg.categories = [sss_rule]
    assert classifier.classify(1_007_200, 0, 1, cfg) == []


def test_missing_readings_do_not_match_rules_that_need_them(cfg):
    cfg.categories = [
        Category(key="s", kind="score", enabled=True, lo=0, hi=2_000_000),
        Category(key="am", kind="am", enabled=True, a_hi=9, m_hi=9, min_rank="D"),
    ]
    assert classifier.classify(None, 0, 0, cfg) == []


# ----------------------------- AJ / FC --------------------------------------
def test_aj_and_fc_are_mutually_exclusive():
    assert classifier.is_aj(OcrRecord(score=1, attack=0, miss=0))
    assert not classifier.is_fc(OcrRecord(score=1, attack=0, miss=0))
    assert classifier.is_fc(OcrRecord(score=1, attack=3, miss=0))
    assert not classifier.is_aj(OcrRecord(score=1, attack=3, miss=0))
    assert not classifier.is_fc(OcrRecord(score=1, attack=3, miss=1))


# ----------------------------- 整理 -----------------------------------------
def test_the_step_order_is_the_nesting_order(cfg):
    rec = OcrRecord(score=1_009_500, attack=0, miss=0)
    cfg.organize.steps = [
        OrganizeStep(kind="date", enabled=True, date_span="month"),
        OrganizeStep(kind="rank", enabled=True),
        OrganizeStep(kind="achievement", enabled=True),
    ]
    assert classifier.organize_rel_path("2026-05-24_08-00-00.png", rec, cfg) == "2026-05/SSS+/AJ"

    cfg.organize.steps.reverse()
    assert classifier.organize_rel_path("2026-05-24_08-00-00.png", rec, cfg) == "AJ/SSS+/2026-05"


def test_a_dimension_with_no_value_is_skipped_not_named_unknown(cfg):
    """取不到值就少一层，不建「未知」文件夹。"""
    cfg.organize.steps = [
        OrganizeStep(kind="date", enabled=True, date_span="day"),
        OrganizeStep(kind="rank", enabled=True),
    ]
    rec = OcrRecord(score=None, attack=None, miss=None)
    assert classifier.organize_rel_path("没有日期的名字.png", rec, cfg) == ""

    rec = OcrRecord(score=1_009_500, attack=0, miss=0)
    assert classifier.organize_rel_path("随手截的.png", rec, cfg) == "SSS+"


def test_date_spans(cfg):
    cfg.organize.steps = [OrganizeStep(kind="date", enabled=True, date_span="year")]
    rec = OcrRecord(score=1, attack=0, miss=0)
    assert classifier.organize_rel_path("2026-05-24_x.png", rec, cfg) == "2026"
    cfg.organize.steps[0].date_span = "month"
    assert classifier.organize_rel_path("2026-05-24_x.png", rec, cfg) == "2026-05"
    cfg.organize.steps[0].date_span = "day"
    assert classifier.organize_rel_path("2026-05-24_x.png", rec, cfg) == "2026-05-24"


def test_an_unrecognised_shot_is_never_moved(cfg, tmp_path):
    """读不到得分＝不是结算截图，壁纸之类的必须留在原地。"""
    cfg.organize.steps = [OrganizeStep(kind="date", enabled=True)]
    shot = _png(Path(cfg.screenshots_dir) / "2026-05-24_08-00-00.png")
    classifier.move_to_organized(shot, OcrRecord(score=None), cfg)
    assert shot.exists()


def test_a_recognised_shot_is_moved_not_copied(cfg, tmp_path):
    cfg.organize.steps = [OrganizeStep(kind="date", enabled=True, date_span="month")]
    shot = _png(Path(cfg.screenshots_dir) / "2026-05-24_08-00-00.png")
    classifier.move_to_organized(shot, OcrRecord(score=1_009_500, attack=0, miss=0), cfg)
    assert not shot.exists()
    assert (Path(cfg.output_root) / "2026-05" / "2026-05-24_08-00-00.png").is_file()


def test_an_identical_file_already_archived_leaves_the_original_alone(cfg):
    """目的地已经有同名同大小的文件时不搬，也不生成 (1) 副本。"""
    cfg.organize.steps = [OrganizeStep(kind="date", enabled=True, date_span="month")]
    name = "2026-05-24_08-00-00.png"
    shot = _png(Path(cfg.screenshots_dir) / name)
    _png(Path(cfg.output_root) / "2026-05" / name)

    classifier.move_to_organized(shot, OcrRecord(score=1_009_500, attack=0, miss=0), cfg)
    assert shot.exists()
    assert not (Path(cfg.output_root) / "2026-05" / f"{name[:-4]} (1).png").exists()


# ----------------------------- 扫描范围 -------------------------------------
def test_our_own_copies_are_excluded_by_location(cfg, sss_rule):
    """规则目录整个跳过，靠位置而不是文件名——用户截图里带 __ 也不会被误伤。"""
    cfg.categories = [sss_rule]
    root = Path(cfg.output_root)
    _png(root / "2026-05-24_08-00-00.png")
    _png(root / "寸" / "SSS寸" / "2026-05-24_08-00-00__SSS寸_SSS_A0M1_1007200.png")
    _png(root / "带__下划线的用户截图.png")

    found = {Path(p).name for p in classifier._list_originals(cfg)}
    assert "2026-05-24_08-00-00.png" in found
    assert "带__下划线的用户截图.png" in found          # 位置对就算原图
    assert not any("SSS寸" in n for n in found)


def test_originals_organized_into_aj_are_still_scanned(cfg):
    """AJ / FC 目录里既有归档原图（要扫）也可能有旧副本（跳过）。"""
    root = Path(cfg.output_root)
    _png(root / "AJ" / "2026-05-24_08-00-00.png")
    _png(root / "AJ" / "2026-05-24_09-00-00__AJ.png")

    found = {Path(p).name for p in classifier._list_originals(cfg)}
    assert "2026-05-24_08-00-00.png" in found
    assert "2026-05-24_09-00-00__AJ.png" not in found


def test_clear_tool_files_only_removes_marked_copies(cfg, sss_rule):
    cfg.categories = [sss_rule]
    root = Path(cfg.output_root)
    copy = _png(root / "寸" / "SSS寸" / "x__SSS寸.png")
    stray = _png(root / "寸" / "SSS寸" / "用户放进来的.png")

    removed = classifier.clear_tool_files(cfg)
    assert removed == 1
    assert not copy.exists()
    assert stray.exists()


# ----------------------------- 复制 -----------------------------------------
def test_a_copy_lands_in_each_rule_folder_with_stats_in_the_name(cfg, sss_rule):
    cfg.categories = [sss_rule]
    shot = _png(Path(cfg.screenshots_dir) / "2026-05-24_08-00-00.png")
    rec = OcrRecord(score=1_007_200, attack=0, miss=1)

    copied = classifier.copy_matches(shot, rec, [sss_rule], cfg)
    assert len(copied) == 1
    assert shot.exists()                                # 原图不动
    # 评级是 SS+（写进文件名时 + 换成 p）：1,007,200 差 300 分够不到 SSS，
    # 这正是「SSS寸」这条规则要抓的东西
    assert Path(copied[0]).name == "2026-05-24_08-00-00__SSS寸_SSp_A0M1_1007200.png"


def test_plus_signs_are_sanitised_out_of_folder_names(cfg):
    """SSS+ 不能直接进文件名，会被换成 SSSp。"""
    rule = Category(key="SSS+寸", kind="score", enabled=True, folder="寸", lo=0, hi=2_000_000)
    cfg.categories = [rule]
    shot = _png(Path(cfg.screenshots_dir) / "a.png")
    copied = classifier.copy_matches(shot, OcrRecord(score=1_009_500, attack=0, miss=0),
                                     [rule], cfg)
    assert "SSSp寸" in Path(copied[0]).name
    assert "SSSp_" in Path(copied[0]).name              # 评级里的 + 也一样


# ----------------------------- 缓存 -----------------------------------------
def test_a_same_named_file_of_a_different_size_is_re_read(cfg, monkeypatch):
    """缓存按裸文件名索引，大小对不上就必须重新识别。"""
    shot = _png(Path(cfg.screenshots_dir) / "a.png", size=100)
    cache = {"a.png": OcrRecord(score=111, attack=0, miss=0, size=9999)}

    calls = []

    class FakeEngine:
        def detect(self, path, _cfg):
            calls.append(path)
            from core.models import OcrResult
            return OcrResult(score=222, attack=1, miss=2)

    rec = classifier.get_ocr(shot, cfg, cache, FakeEngine())
    assert calls, "大小不匹配却复用了缓存"
    assert rec.score == 222


def test_a_legacy_record_without_a_size_is_still_trusted(cfg):
    shot = _png(Path(cfg.screenshots_dir) / "a.png")
    cache = {"a.png": OcrRecord(score=111, attack=0, miss=0, size=None)}

    class ExplodingEngine:
        def detect(self, *_a):
            raise AssertionError("不该重新识别老记录")

    assert classifier.get_ocr(shot, cfg, cache, ExplodingEngine()).score == 111


# ----------------------------- 统计 -----------------------------------------
def test_daily_counts_group_by_the_date_in_the_filename(cfg, sss_rule):
    cfg.categories = [sss_rule]
    cache = {
        "2026-05-24_08-00-00.png": OcrRecord(score=1_007_200, attack=0, miss=1),
        "2026-05-24_09-00-00.png": OcrRecord(score=1_009_900, attack=0, miss=0),
        "2026-05-25_08-00-00.png": OcrRecord(score=1_009_000, attack=2, miss=0),
        "没有日期.png": OcrRecord(score=1_007_200, attack=0, miss=1),
    }
    rows = classifier.daily_counts(cfg, cache)
    assert rows == [("2026-05-24", 1, 1, 0), ("2026-05-25", 0, 0, 1)]
