# -*- coding: utf-8 -*-
"""配置的读写、迁移、路径推导。"""

from __future__ import annotations

import json

from core import config as config_mod
from core import paths
from core.models import Category, CunConfig, OrganizeStep


def test_a_saved_config_round_trips(isolated_data_dir):
    cfg = CunConfig()
    cfg.game_root = r"D:\CHUNITHM"
    cfg.screenshots_dir = r"D:\CHUNITHM\bin\screenshots"
    cfg.dghub.enabled = True
    cfg.dghub.port = 9001
    cfg.capture.enabled = True
    cfg.capture.delay_s = 3.5
    cfg.categories = [Category(key="AJ寸", label="AJ寸", kind="ajcun",
                               enabled=True, folder="寸/AJ寸", custom=True, m_hi=3)]
    config_mod.save(cfg)

    back = config_mod.load()
    assert back.game_root == cfg.game_root
    assert back.dghub.port == 9001
    assert back.capture.delay_s == 3.5
    assert len(back.categories) == 1
    assert back.categories[0].m_hi == 3


def test_chinese_folder_names_are_not_escaped(isolated_data_dir):
    """配置文件要人能看懂，「寸」不该变成 \\u5bf8。"""
    config_mod.save(CunConfig())
    raw = paths.config_path().read_text(encoding="utf-8")
    assert '"寸"' in raw
    assert "\\u" not in raw


def test_legacy_builtin_rules_are_dropped_but_user_rules_survive(isolated_data_dir):
    """v1.1→v1.2 迁移：只丢内置预设，其它一条都不能少。"""
    raw = {
        "categories": [
            {"key": "SSS寸", "label": "SSS寸", "kind": "score", "enabled": True},
            {"key": "我自己加的", "label": "我自己加的", "kind": "ajcun", "enabled": True},
        ]
    }
    paths.config_path().write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    cfg = config_mod.load()
    keys = [c.key for c in cfg.categories]
    assert "SSS寸" not in keys
    assert "我自己加的" in keys
    assert cfg.categories[0].custom is True     # 幸存者一律标成自定义


def test_organize_steps_are_completed_and_deduped(isolated_data_dir):
    """缺的补上、重的去掉、未知的丢掉，但用户的排序要保住。"""
    cfg = CunConfig()
    cfg.organize.steps = [
        OrganizeStep(kind="rank", enabled=True),
        OrganizeStep(kind="rank"),
        OrganizeStep(kind="没这个维度"),
    ]
    config_mod.save(cfg)

    back = config_mod.load()
    kinds = [s.kind for s in back.organize.steps]
    assert kinds[0] == "rank"                   # 用户排在最前的还在最前
    assert sorted(kinds) == ["achievement", "date", "rank"]
    assert back.organize.steps[0].enabled is True


def test_rank_of_uses_the_highest_matching_threshold():
    cfg = CunConfig()
    assert config_mod.rank_of(1_009_000, cfg) == "SSS+"
    assert config_mod.rank_of(1_008_999, cfg) == "SSS"
    assert config_mod.rank_of(0, cfg) == "D"
    assert config_mod.rank_of(None, cfg) is None


# ----------------------------- 游戏目录 -------------------------------------
def test_a_game_root_is_recognised_by_its_bin_folder(game_tree):
    assert config_mod.looks_like_game_root(game_tree)
    assert config_mod.normalize_game_root(game_tree) == game_tree
    # 选中 bin 也接受，归一到上一级
    assert config_mod.normalize_game_root(game_tree / "bin") == game_tree


def test_an_unrelated_folder_is_rejected(tmp_path):
    plain = tmp_path / "随便一个目录"
    plain.mkdir()
    assert not config_mod.looks_like_game_root(plain)
    assert config_mod.normalize_game_root(plain) is None


def test_applying_a_game_root_fills_the_derived_paths(game_tree):
    cfg = CunConfig()
    config_mod.apply_game_root(cfg, game_tree)
    assert cfg.game_root == str(game_tree)
    assert cfg.screenshots_dir == str(game_tree / "bin" / "screenshots")
    assert cfg.output_root == cfg.screenshots_dir
    assert cfg.start_bat == str(game_tree / "start.bat")


def test_moving_the_game_takes_the_derived_paths_along(tmp_path, game_tree):
    """换游戏安装位置，之前**推导出来的**路径要跟着走。"""
    cfg = CunConfig()
    config_mod.apply_game_root(cfg, game_tree)

    moved = tmp_path / "另一个盘" / "CHUNITHM"
    (moved / "bin" / "screenshots").mkdir(parents=True)
    (moved / "start.bat").write_bytes(b"@echo off\r\n")
    config_mod.apply_game_root(cfg, moved)

    assert cfg.screenshots_dir == str(moved / "bin" / "screenshots")
    assert cfg.output_root == cfg.screenshots_dir
    assert cfg.start_bat == str(moved / "start.bat")


def test_a_hand_picked_screenshots_dir_is_never_clobbered(tmp_path, game_tree):
    """用户自己指定过的目录，换游戏目录时不能被顶掉。"""
    custom = tmp_path / "我自己的截图库"
    custom.mkdir()
    cfg = CunConfig()
    cfg.screenshots_dir = str(custom)
    cfg.output_root = str(custom)

    config_mod.apply_game_root(cfg, game_tree)
    assert cfg.screenshots_dir == str(custom)
    assert cfg.output_root == str(custom)
    assert cfg.game_root == str(game_tree)      # 游戏目录本身还是记下来了


def test_the_installer_hint_seeds_the_config_once(isolated_data_dir, game_tree, monkeypatch):
    """安装器写的 install.ini 第一次运行时被吃掉。"""
    ini = isolated_data_dir / "install.ini"
    ini.write_text(f"[cun]\ngame_root={game_tree}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "install_ini_path", lambda: ini)

    cfg = config_mod.load()
    assert cfg.game_root == str(game_tree)
    assert cfg.screenshots_dir == str(game_tree / "bin" / "screenshots")


def test_the_installer_hint_does_not_override_a_configured_dir(
        isolated_data_dir, game_tree, tmp_path, monkeypatch):
    """重装不能把用户后来改过的截图目录顶回去。"""
    mine = tmp_path / "我改过的"
    mine.mkdir()
    cfg = CunConfig()
    cfg.screenshots_dir = str(mine)
    config_mod.save(cfg)

    ini = isolated_data_dir / "install.ini"
    ini.write_text(f"[cun]\ngame_root={game_tree}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "install_ini_path", lambda: ini)

    assert config_mod.load().screenshots_dir == str(mine)


def test_a_stray_config_up_the_tree_does_not_trigger_portable_mode(
        isolated_data_dir, tmp_path, monkeypatch):
    """仓库里放一份种子配置，不该让运行中的程序误判成便携部署。

    踩过：源码运行时 ``portable_dir()`` 找到仓库根的 cun_config.json，
    截图目录被推到仓库旁边去了。
    """
    fake_exe_dir = tmp_path / "repo" / "sub"
    fake_exe_dir.mkdir(parents=True)
    (tmp_path / "repo" / "cun_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "exe_dir", lambda: fake_exe_dir)

    cfg = config_mod.load()
    assert cfg.screenshots_dir == ""             # 没有游戏目录就该是空的
