"""
API v2 模块初始化

注册所有 v2 版本的 API 蓝图
"""

from flask import Flask


def register_v2_blueprints(app: Flask):
    """注册 v2 版本的所有蓝图"""
    from .backup import bp as backup_bp
    
    app.register_blueprint(backup_bp)
