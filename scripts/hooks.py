"""构建只操作暂存目录，不回写人工 Markdown。"""
import copy
import hashlib
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
    # 保留旧段落锚点，已有分享链接仍可访问。
    target_number = 0
    for block in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'tr']):
        if block.find_parent(class_='chapter-overview') or not block.get_text(strip=True):
            continue
        target_number += 1
        if not block.get('id'):
            block['id'] = 'search-target-%d' % target_number
    sections = []
    entries = []
    duplicates = {}
    for block in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'p', 'tr']):
        if block.find_parent(class_='chapter-overview'):
            continue
        # 列表子步骤独立定位；段落归入所属步骤，避免重复收录。
        if block.name != 'li' and block.find_parent(['li', 'tr']):
            continue
        content = copy.copy(block)
        if block.name == 'li':
            for nested in content.find_all(['ol', 'ul']):
                nested.decompose()
        text = ' '.join(content.get_text(' ', strip=True).split())
        if not text:
            continue
        if block.name.startswith('h'):
            level = int(block.name[1])
            sections = [(depth, title) for depth, title in sections if depth < level]
            sections.append((level, text))
        labels = []
        if block.name == 'li':
            for step in list(reversed(block.find_parents('li'))) + [block]:
                if step.parent.name != 'ol':
                    continue
                number = int(step.parent.get('start', 1))
                for sibling in step.parent.find_all('li', recursive=False):
                    number = int(sibling.get('value', number))
                    if sibling is step:
                        break
                    number += 1
                labels.append('第 %d 步' % number)
        label = ' › '.join(labels)
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
        duplicates[digest] = duplicates.get(digest, 0) + 1
        anchor = 'search-block-' + digest + '-%d' % duplicates[digest]
        # 在块内设置独立锚点，不改变标题和旧段落的 ID。
        marker = soup.new_tag('span', id=anchor)
        marker['class'] = 'search-anchor'
        container = block.find(['td', 'th']) if block.name == 'tr' else block
        if container is None:
            continue
        container.insert(0, marker)
        block['data-search-block'] = anchor
        parent_step = block.find_parent('li')
        parent_text = ''
        if parent_step is not None:
            parent_content = copy.copy(parent_step)
            for nested in parent_content.find_all(['ol', 'ul']):
                nested.decompose()
            parent_text = ' '.join(parent_content.get_text(' ', strip=True).split())
        entries.append({
            'location': page.url + '#' + anchor,
            'page_title': page.title,
            'section_title': ' › '.join(title for _, title in sections if title != page.title),
            'step_label': label,
            'parent_text': parent_text,
            'text': text
        })
    for index, entry in enumerate(entries):
        entry['before'] = entries[index - 1]['text'] if index else ''
        entry['after'] = entries[index + 1]['text'] if index + 1 < len(entries) else ''
    exact_search_entries.extend(entries)
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
