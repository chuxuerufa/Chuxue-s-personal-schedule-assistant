"""
PythonAnywhere WSGI 配置
部署时将此文件放到 /home/<你的用户名>/mysite/ 目录
或直接在 PythonAnywhere 的 Web 配置页面粘贴内容

重要：部署后把下面路径改成你的实际用户名
"""
import sys

# 改这里 → 你的 PythonAnywhere 用户名
PA_USER = "你的用户名"

project_home = f"/home/{PA_USER}/study-planner"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 确保 data 目录存在
import os
os.makedirs(os.path.join(project_home, "data"), exist_ok=True)

from app import app as application
