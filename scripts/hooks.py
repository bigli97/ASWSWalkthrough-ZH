"""构建只操作暂存目录，不回写人工 Markdown。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import site_project

def on_config(config):
    site_project.stage()
    config['nav'] = site_project.navigation()
    return config

def on_pre_build(config):
    site_project.stage()

def on_serve(server, config, builder):
    # 只监听人工输入；暂存写入不能再次触发构建。
    server.unwatch(config.docs_dir)
    return server
