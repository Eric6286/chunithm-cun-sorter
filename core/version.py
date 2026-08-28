# -*- coding: utf-8 -*-
"""版本号与应用标识的唯一真源。

打包脚本、安装器文件名、控制面板里的卸载项版本全部从这里读，别在别处再写一份。
"""

__version__ = "2.0.1"

APP_NAME = "今天你寸了吗"
APP_SLUG = "chunithm-cun-sorter"
APP_USER_MODEL_ID = "JinTianNiCunLeMa.App"

#: 单实例互斥体名，与 v1.x 保持一致，避免新旧版同时跑两个监视器
SINGLE_INSTANCE_MUTEX = "chunithm-cun-sorter-single-instance"
