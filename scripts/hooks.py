"""构建只操作暂存目录，不回写人工 Markdown。"""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parent))
import site_project

exact_search_entries = []

def on_config(config):
    site_project.stage()
    config['nav'] = site_project.navigation()
    return config

def on_pre_build(config):
    exact_search_entries[:] = []
    site_project.stage()

def on_page_content(html, page, config, files):
    search = page.meta.get('search') or {}
    if search.get('exclude'):
        return html
    soup = BeautifulSoup(html, 'html.parser')
    section_title = page.title
    target_number = 0
    for block in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'tr']):
        classes = []
        for parent in block.parents:
            classes.extend(parent.get('class') or [])
        if 'chapter-overview' in classes:
            continue
        text = ' '.join(block.get_text(' ', strip=True).split())
        if not text:
            continue
        if block.name.startswith('h'):
            section_title = text
        target_number += 1
        if not block.get('id'):
            block['id'] = 'search-target-%d' % target_number
        exact_search_entries.append({
            'location': page.url + '#' + block['id'],
            'page_title': page.title,
            'section_title': section_title,
            'text': text
        })
    return str(soup)

def on_post_build(config):
    destination = Path(config['site_dir']) / 'search' / 'search_exact_index.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'entries': exact_search_entries}, ensure_ascii=False,
                                       separators=(',', ':')), encoding='utf-8')

def on_serve(server, config, builder):
    # 只监听人工输入；暂存写入不能再次触发构建。
    server.unwatch(config.docs_dir)
    return server
