# -*- coding: utf-8 -*-
"""业务模型层：解析各类 HOI4 数据，允许互相依赖，不许 import api。

P0-3 按依赖从少到多迁入 12 个模块：
    diagnose / idea / tech / equipment / event / decision / character
    country / state / map / focus / world
"""
