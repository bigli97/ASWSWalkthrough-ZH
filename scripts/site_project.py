"""这一份攻略的提取、拼接、校验与本地构建；不调用外部翻译 API。"""
import argparse
import fcntl
from collections import Counter
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'ASWSWalkthrough'
TRANS = ROOT / 'translation'
BUILD = ROOT / '.build' / 'docs'
SAMPLES = ['wt-info', 'wt-tips', 'wt-intro']
TITLES = {'wt-info': '基本信息', 'wt-tips': '技巧与窍门', 'wt-intro': '序章',
          'wt-house': '房屋翻修', 'wt-mc': '主角', 'wt-mira': '米拉',
          'wt-carmen': '卡门', 'wt-lucius': '卢修斯', 'wt-verena': '维蕾娜',
          'wt-rose': '罗斯', 'wt-corven': '科文', 'wt-john': '约翰',
          'wt-melissa': '梅丽莎', 'wt-imawyn': '伊玛温', 'wt-maui': '毛伊',
          'wt-church': '教堂', 'wt-monastery': '修道院', 'wt-katherin': '凯瑟琳',
          'wt-kate': '凯特', 'wt-claire': '克莱尔', 'wt-frisha': '弗莉莎',
          'wt-bianca': '比安卡', 'wt-gavina': '加维娜', 'wt-ugotha': '乌戈莎',
          'wt-snikka': '斯尼卡', 'wt-natasha': '娜塔莎', 'wt-ophilia': '奥菲莉娅',
          'wt-anya': '安雅', 'wt-penny': '佩妮', 'wt-lilly': '莉莉',
          'wt-elisabeth': '伊丽莎白', 'wt-gwen': '格温', 'wt-sabrina': '萨布丽娜',
          'wt-athia': '阿西娅', 'wt-bridget': '布丽姬特', 'wt-agatha': '阿加莎',
          'wt-heather': '希瑟', 'wt-rumah': '鲁玛村', 'wt-raaisha': '拉伊莎',
          'wt-hiba': '希芭', 'wt-nyra': '妮拉', 'wt-umah': '乌玛',
          'wt-darkholt': '重建暗林', 'wt-mansion': '市长宅邸', 'wt-julia': '朱莉娅',
          'wt-liandra': '莉安德拉', 'wt-helena': '海伦娜', 'wt-yasmine': '雅斯敏'}
PLACES = {'wt-house', 'wt-church', 'wt-monastery', 'wt-rumah', 'wt-darkholt', 'wt-mansion'}


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSON 存在重复块编号：' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def manifest():
    return read_json(TRANS / 'chapters.json')


class GuideMarkdown(MarkdownConverter):
    def convert_li(self, el, text, parent_tags):
        text = (text or '').strip()
        if not text:
            return '\n'
        parent = el.parent
        prefix = (str(int(parent.get('start', 1)) + len(el.find_previous_siblings('li'))) + '. ') if parent.name == 'ol' else '- '
        return prefix + text.replace('\n', '\n    ') + '\n'


def md(fragment):
    return GuideMarkdown(heading_style='ATX', bullets='-', escape_underscores=False).convert(str(fragment)).strip()


def extract():
    index = BeautifulSoup((SOURCE / 'index.html').read_text(), 'html.parser')
    entries = index.select('#menu .wt-link[data-target]')
    chapters = []
    for order, entry in enumerate(entries, 1):
        ident = entry['data-target']
        chapters.append({'id': ident, 'order': order, 'title': entry.get_text(strip=True),
                         'file': '%02d-%s.md' % (order, ident[3:]),
                         'category': '入门与玩法' if order <= 5 else ('地区与建设' if ident in PLACES else '人物')})
    paths = {x['id']: x['file'] for x in chapters}
    if set(paths) != {p.stem for p in (SOURCE / 'pages').glob('*.html')}:
        raise ValueError('入口与页面目录不一致，需要检查未登记或缺失的页面。')
    pages = {c['id']: (SOURCE / 'pages' / (c['id'] + '.html')).read_text() for c in chapters}
    versions = re.findall(r'new-(\d+-\d+-\d+-\d+)', ''.join(pages.values()))
    version = '.'.join(map(str, max(tuple(map(int, v.split('-'))) for v in versions)))
    paths['hidden-sections'] = 'original-ui.md'
    for c in chapters:
        # 源码有未闭合标签；与浏览器相同的 HTML5 修复规则避免吞并后续列表项。
        soup = BeautifulSoup(pages[c['id']], 'html5lib').body
        c['images'] = [img['src'] for img in soup.select('img[src]')]
        c['links'] = [a['data-target'] for a in soup.select('[data-target]')]
        c['list_items'] = len(soup.select('li'))
        c['headings'] = len(soup.select('h3'))
        # 检查每个源文字节点均进入一个分块，不把嵌套列表扁平化。
        latest = soup.select_one('#latest-version')
        if latest is not None:
            latest.string = version
        for a in soup.select('[data-target]'):
            target = a['data-target']
            if target not in paths:
                raise ValueError('未知章节链接：' + target)
            a.name = 'a'
            a['href'] = paths[target]
        for image in soup.select('img'):
            filename = Path(image['src']).name
            if not (SOURCE / 'images' / filename).is_file():
                raise ValueError('图片缺失：' + filename)
            image['src'] = 'assets/images/' + filename
            image['alt'] = image.get('alt') or filename
        for heading in soup.select('h3'):
            heading.name = 'h2'
        consumed, blocks = [], []
        for node in soup.contents:
            if isinstance(node, NavigableString) and not node.strip():
                continue
            nodes = node.find_all('li', recursive=False) if isinstance(node, Tag) and node.name in ('ol', 'ul') else [node]
            for offset, item in enumerate(nodes):
                consumed.extend([str(t) for t in item.descendants if isinstance(t, NavigableString)] if isinstance(item, Tag) else [str(item)])
                if isinstance(node, Tag) and node.name in ('ol', 'ul'):
                    body = md(''.join(str(x) for x in item.contents))
                    prefix = str(int(node.get('start', 1)) + offset) + '. ' if node.name == 'ol' else '- '
                    rendered = prefix + body.replace('\n', '\n    ')
                else:
                    rendered = md(item)
                if not rendered:
                    continue
                classes = list(item.get('class', [])) if isinstance(item, Tag) else []
                if isinstance(node, Tag):
                    classes += list(node.get('class', []))
                block = {'id': '%04d' % (len(blocks) + 1), 'markdown': rendered, 'classes': sorted(set(classes))}
                blocks.append(block)
        all_text = [str(t) for t in soup.descendants if isinstance(t, NavigableString) and t.strip()]
        if Counter(t for t in consumed if t.strip()) != Counter(all_text):
            raise ValueError('提取文字覆盖检查失败：' + c['id'])
        data = {'chapter': c['id'], 'title': c['title'], 'blocks': blocks}
        destination = TRANS / 'source' / (c['id'] + '.json')
        # 轻量保护：已存在草稿时拒绝悄悄变更对应原文，后续可另行做版本更新。
        if destination.exists() and read_json(destination) != data and (TRANS / 'drafts' / c['id']).exists():
            raise ValueError('已有草稿的原文发生变化，请单独处理更新：' + c['id'])
        dump(destination, data)
        write(TRANS / 'source' / (c['id'] + '.md'), '# ' + c['title'] + '\n\n' + '\n\n'.join(b['markdown'] for b in blocks) + '\n')
        # 批次按结构单元组合；单个长列表项保持完整，不切断条件句。
        batches, current, size = [], [], 0
        for b in blocks:
            if current and size + len(b['markdown']) > 1800:
                batches.append(current)
                current, size = [], 0
            current.append(b['id'])
            size += len(b['markdown'])
        if current:
            batches.append(current)
        c['batches'] = batches
        c['blocks'] = len(blocks)
    dump(TRANS / 'chapters.json', {'version': version, 'chapters': chapters, 'samples': SAMPLES})
    (ROOT / 'page').mkdir(exist_ok=True)
    shutil.copy2(SOURCE / 'index.html', ROOT / 'page' / 'index.html')
    shutil.copytree(SOURCE / 'pages', ROOT / 'page' / 'pages', dirs_exist_ok=True)
    shutil.copytree(SOURCE / 'images', ROOT / 'page' / 'images', dirs_exist_ok=True)
    for image in (SOURCE / 'images').iterdir():
        target = ROOT / 'docs' / 'assets' / 'images' / image.name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, target)
    print('已提取 %s 章，原文字节点覆盖检查通过；版本 %s。' % (len(chapters), version))
    pending()


def pending():
    data = manifest()
    remaining = []
    glossary = (ROOT / 'glossary.md').read_text() if (ROOT / 'glossary.md').exists() else ''
    rules_path = ROOT / 'translation-rules.md'
    if not rules_path.exists():
        raise ValueError('缺少翻译规则文件：' + str(rules_path))
    translation_rules = rules_path.read_text(encoding='utf-8')
    for c in data['chapters']:
        if c['id'] not in data['samples']:
            continue
        blocks = read_json(TRANS / 'source' / (c['id'] + '.json'))['blocks']
        lookup = {b['id']: b for b in blocks}
        for i, ids in enumerate(c['batches'], 1):
            target = TRANS / 'drafts' / c['id'] / ('%03d.json' % i)
            if target.exists():
                validate_batch(target, ids, lookup)
                continue
            pack = {'chapter': c['id'], 'batch': i, 'output': str(target.relative_to(ROOT)),
                    'instruction': '翻译前先阅读 translation_rules 和 glossary。逐块完整翻译，不摘要、不增删条件；保留编号、链接、图片和加粗。返回以原块 ID 为键、中文 Markdown 为值的 JSON。不可改写已有草稿或 docs。',
                    'translation_rules': translation_rules, 'glossary': glossary, 'blocks': [lookup[x] for x in ids]}
            dump(TRANS / 'requests' / c['id'] / ('%03d.json' % i), pack)
            remaining.append('%s/%03d' % (c['id'], i))
    dump(TRANS / 'pending.json', remaining)
    print('待翻译样例批次：' + ('、'.join(remaining) if remaining else '无'))


def signatures(text):
    return {'links': Counter(re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)),
            'numbers': Counter(re.findall(r'\d+', re.sub(r'!?\[[^\]]*\]\([^)]+\)', '', text))),
            'headings': Counter(re.findall(r'^#{1,6} ', text, re.M)),
            'list': Counter(re.findall(r'^\s*(?:\d+\.|-) ', text, re.M)),
            'bold': text.count('**')}


def validate_batch(path, ids, lookup):
    translated = read_json(path)
    if set(translated) != set(ids):
        raise ValueError('草稿块编号不完整或重复范围：' + str(path))
    for ident in ids:
        value = translated[ident]
        if not isinstance(value, str) or not re.search(r'[\u4e00-\u9fff]', value):
            raise ValueError('中文译文为空：' + ident)
        if signatures(lookup[ident]['markdown']) != signatures(value):
            raise ValueError('链接、数字、标题、列表或加粗结构不一致：%s/%s' % (path, ident))
    return translated


def assemble():
    data = manifest()
    for c in data['chapters']:
        if c['id'] not in data['samples']:
            continue
        destination = ROOT / 'docs' / c['file']
        if destination.exists():
            print('保留现有中文：' + c['file'])
            continue
        blocks = read_json(TRANS / 'source' / (c['id'] + '.json'))['blocks']
        lookup = {b['id']: b for b in blocks}
        translated = {}
        for i, ids in enumerate(c['batches'], 1):
            path = TRANS / 'drafts' / c['id'] / ('%03d.json' % i)
            if not path.exists():
                print('草稿尚未齐全，暂不生成：' + c['file'])
                break
            translated.update(validate_batch(path, ids, lookup))
        else:
            content = ['# ' + TITLES.get(c['id'], c['title']),
                       '> 本章为中文初译，待人工审核。原文版本：' + data['version'] + '。']
            for b in blocks:
                # 标记保留用于覆盖比对，不影响网页阅读与人工正文编辑。
                content.append('<!-- source:%s -->\n%s' % (b['id'], translated[b['id']]))
                versions = [x[4:].replace('-', '.') for x in b['classes'] if x.startswith('new-')]
                if versions:
                    content.append('> 原文版本标记：' + '、'.join(versions) + ' 新增。')
            if c['id'] == 'wt-info':
                content.insert(2, '!!! note "原站界面说明"\n    下文关于绿色高亮、右侧菜单和 Cookie 的说明属于原站。本站保留这些原文信息；本站不提供隐藏章节功能。')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('x', encoding='utf-8') as out:
                out.write('\n\n'.join(content) + '\n')
            print('已创建中文章节：' + c['file'])
    pending()


CSS = '''
:root { --md-text-font: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }
.md-grid { max-width: 1440px; }
.md-typeset { font-size: .82rem; line-height: 1.85; }
.md-typeset h1 { color: #173c69; font-weight: 700; letter-spacing: -.02em; }
.md-typeset h2 { border-bottom: 1px solid #dce6f2; padding-bottom: .35em; font-weight: 650; }
.md-typeset img { border-radius: 8px; border: 1px solid #dce6f2; max-height: 640px; }
.md-typeset li { margin-bottom: .65em; }
.md-typeset blockquote { border-color: #2780d8; color: #526780; background: #f3f7fc; padding: .7em 1em; }
.md-typeset a { text-underline-offset: .2em; }
@media (max-width: 700px) { .md-typeset { font-size: .8rem; } }
'''


def stage():
    (ROOT / '.build').mkdir(exist_ok=True)
    with (ROOT / '.build' / 'stage.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _stage()


def _stage():
    data = manifest()
    BUILD.mkdir(parents=True, exist_ok=True)
    terms = []
    for row in (ROOT / 'glossary.md').read_text().splitlines():
        columns = row.split('|')
        if len(columns) >= 4:
            terms.extend(re.findall(r'[\u4e00-\u9fff]{2,}', columns[2]))
    write(ROOT / '.build' / 'jieba-user.txt', '\n'.join(word + ' 100000' for word in sorted(set(terms))) + '\n')
    # 暂存可重新生成；docs 永远只读。清除已删除章节的旧副本。
    for path in BUILD.glob('*.md'):
        path.unlink()
    shutil.copytree(ROOT / 'docs', BUILD, dirs_exist_ok=True)
    for path in (ROOT / 'docs').glob('*.md'):
        # 去掉构建用的块标记，防止注释将连续列表切成多个列表。
        text = re.sub(r'<!-- source:\d+ -->\n', '', path.read_text())
        write(BUILD / path.name, text)
    shutil.copytree(ROOT / 'page' / 'images', BUILD / 'assets' / 'images', dirs_exist_ok=True)
    write(BUILD / 'assets' / 'site.css', CSS)
    write(BUILD / 'glossary.md', '---\nsearch:\n  boost: 0.1\n---\n\n' + (ROOT / 'glossary.md').read_text())
    write(BUILD / 'original-ui.md', '# 原站隐藏章节功能\n\n原站可通过标题栏的 hide 隐藏章节；被隐藏章节可在管理列表恢复，新版本可能自动恢复显示。Cookie 仅用于记录隐藏选择。中文站不启用此功能。\n')
    rows = ['# 全部章节', '', '按原站入口排序。当前仅发布 3 章中文初译；其他章节提供本地英文原文，不表示已完成翻译。', '', '| 顺序 | 章节 | 分类 | 状态 |', '| --- | --- | --- | --- |']
    local_paths = {c['id']: c['file'].replace('.md', '.html') for c in data['chapters']}
    local_paths['hidden-sections'] = 'original-ui.html'
    for c in data['chapters']:
        available = (ROOT / 'docs' / c['file']).exists()
        title = TITLES.get(c['id'], c['title'])
        rows.append('| %02d | [%s](%s) | %s | %s |' % (c['order'], title, c['file'], c['category'], '中文初译' if available else '待翻译'))
        if not available:
            write(BUILD / c['file'], '---\nsearch:\n  exclude: true\n---\n\n# ' + c['title'] + '\n\n本章尚未翻译，未纳入第一阶段样例。\n\n[阅读本地英文原文](reference/' + c['id'] + '.html) · [返回全部章节](catalog.md)\n')
        raw = BeautifulSoup((ROOT / 'page' / 'pages' / (c['id'] + '.html')).read_text(), 'html.parser')
        for a in raw.select('[data-target]'):
            a.name = 'a'
            a['href'] = '../' + local_paths[a['data-target']]
        for img in raw.select('img'):
            img['src'] = '../assets/images/' + Path(img['src']).name
        v = raw.select_one('#latest-version')
        if v is not None:
            v.string = data['version']
        write(BUILD / 'reference' / (c['id'] + '.html'), '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(c['title']) + '</title><style>body{max-width:900px;margin:30px auto;padding:0 20px;font:17px/1.8 system-ui}img{max-width:100%}a{color:#1769aa}</style><p><a href="../catalog.html">返回中文攻略目录</a> · 未翻译原文</p><h1>' + html.escape(c['title']) + '</h1>' + str(raw) + '</html>')
    write(BUILD / 'catalog.md', '\n'.join(rows) + '\n')
    for name in ['index.md', 'catalog.md', 'original-ui.md']:
        path = BUILD / name
        write(path, '---\nsearch:\n  exclude: true\n---\n\n' + path.read_text())


def navigation():
    nav = [{'攻略首页': 'index.md'}, {'全部章节与进度': 'catalog.md'}]
    for category in ['入门与玩法', '地区与建设', '人物']:
        items = []
        for c in manifest()['chapters']:
            if c['category'] == category:
                title = TITLES.get(c['id'], c['title'])
                if not (ROOT / 'docs' / c['file']).exists():
                    title += ' · 待译'
                items.append({title: c['file']})
        nav.append({category: items})
    nav += [{'术语表': 'glossary.md'}, {'原站界面说明': 'original-ui.md'}]
    return nav


def reviewed_chapters():
    chapters = []
    for chapter in manifest()['chapters']:
        path = ROOT / 'docs' / chapter['file']
        if not path.exists():
            continue
        content = path.read_text(encoding='utf-8')
        if '> 本章中文译文已通过人工审核。' not in content:
            continue
        title = re.search(r'^# (.+)$', content, re.M)
        if title is None:
            raise ValueError('已审核章节缺少一级标题：' + chapter['file'])
        chapters.append((title.group(1), chapter['file']))
    if not chapters:
        raise ValueError('未找到已审核的中文章节，无法同步发布信息。')
    return chapters


def sync_marked_section(path, pattern, content, label):
    text = path.read_text(encoding='utf-8')
    match = re.search(pattern, text, re.S)
    if match is None:
        raise ValueError('%s 缺少自动同步标记，无法同步。' % label)
    updated = text[:match.start(2)] + content + text[match.start(3):]
    if updated != text:
        write(path, updated)


def sync_readme():
    chapters = reviewed_chapters()
    sync_marked_section(ROOT / 'README.md', r'(<!-- reviewed-chapters:start -->\n)(.*?)(<!-- reviewed-chapters:end -->)',
                        '\n'.join('- ' + title for title, unused in chapters) + '\n', 'README')
    print('README 已同步 %d 个已审核章节。' % len(chapters))


def sync_homepage():
    chapters = reviewed_chapters()
    content = ('当前版本 **%s**，已通过人工审核的中文章节共 **%d** 章。\n\n### 开始阅读\n\n' %
               (manifest()['version'], len(chapters)))
    content += '\n\n'.join('- [%s](%s)' % chapter for chapter in chapters) + '\n'
    sync_marked_section(ROOT / 'docs' / 'index.md', r'(<!-- homepage-reviewed:start -->\n)(.*?)(<!-- homepage-reviewed:end -->)',
                        content, '首页')
    print('首页已同步 %d 个已审核章节。' % len(chapters))


def check():
    data = manifest()
    report = {'chapters': len(data['chapters']), 'samples': [], 'site_links_checked': 0}
    for c in data['chapters']:
        if c['id'] not in data['samples']:
            continue
        blocks = read_json(TRANS / 'source' / (c['id'] + '.json'))['blocks']
        lookup = {b['id']: b for b in blocks}
        for i, ids in enumerate(c['batches'], 1):
            validate_batch(TRANS / 'drafts' / c['id'] / ('%03d.json' % i), ids, lookup)
        text = (ROOT / 'docs' / c['file']).read_text()
        if re.findall(r'<!-- source:(\d+) -->', text) != [b['id'] for b in blocks]:
            raise ValueError('中文章节块标记缺失或顺序变化：' + c['file'])
        report['samples'].append({'chapter': c['id'], 'blocks': len(blocks), 'images': len(c['images']), 'list_items': c['list_items']})
    site = ROOT / 'dist' / 'site'
    site_url = re.search(r'^site_url:\s*(\S+)', (ROOT / 'mkdocs.yml').read_text(), re.M)
    site_path = urlsplit(site_url.group(1)).path.rstrip('/') if site_url else ''
    if site.exists():
        for path in site.rglob('*.html'):
            soup = BeautifulSoup(path.read_text(), 'html.parser')
            for node in soup.select('[href], [src]'):
                url = node.get('href') or node.get('src')
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or url.startswith('data:'):
                    continue
                if site_path and parsed.path.startswith(site_path + '/'):
                    target = site / unquote(parsed.path[len(site_path) + 1:])
                else:
                    target = (site / unquote(parsed.path).lstrip('/')) if parsed.path.startswith('/') else (path.parent / unquote(parsed.path))
                target = target.resolve() if parsed.path else path
                if target.is_dir():
                    target /= 'index.html'
                if not target.exists():
                    raise ValueError('本地链接不存在：%s → %s' % (path, url))
                if parsed.fragment and target.suffix == '.html':
                    doc = BeautifulSoup(target.read_text(), 'html.parser')
                    if not doc.find(id=unquote(parsed.fragment)):
                        raise ValueError('锚点不存在：%s → %s' % (path, url))
                report['site_links_checked'] += 1
    dump(TRANS / 'validation.json', report)
    print('校验通过：草稿结构、中文块顺序、图片、链接及锚点。检查 %d 个本地引用。' % report['site_links_checked'])


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def pdf():
    if not shutil.which('pandoc'):
        raise ValueError('请先安装 Pandoc，再运行 make pdf。')
    stage()
    documents, combined = [], []
    for c in manifest()['chapters']:
        path = ROOT / 'docs' / c['file']
        if path.exists():
            documents.append(c)
    files = {c['file']: c['id'] for c in documents}
    for c in documents:
        text = (ROOT / 'docs' / c['file']).read_text()
        text = re.sub(r'<!-- source:\d+ -->\s*', '', text)
        text = re.sub(r'^# (.+)$', r'# \1 {#' + c['id'] + '}', text, count=1, flags=re.M)
        # Pandoc 不支持 MkDocs 提示框语法，保留其完整文字为引用。
        text = re.sub(r'^!!! \w+ "([^"]+)"\n((?:    .*\n?)+)', lambda m: '> **' + m[1] + '**\n> ' + m[2].replace('    ', '').replace('\n', '\n> ') + '\n', text, flags=re.M)
        def link(m):
            label, target = m[1], m[2]
            if target in files:
                return '[' + label + '](#' + files[target] + ')'
            return label + '（相关章节未收入本 PDF）'
        text = re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+\.md)\)', link, text)
        combined.append(text)
    output = ROOT / 'dist' / 'pdf'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BUILD / 'assets' / 'images', output / 'assets' / 'images', dirs_exist_ok=True)
    merged = output / 'walkthrough-zh.md'
    write(merged, '\n\n'.join(combined))
    typ = output / 'walkthrough-zh.typ'
    run('pandoc', str(merged), '--from=markdown', '--to=typst', '--standalone', '--toc', '--toc-depth=2', '--resource-path=' + str(BUILD), '-V', 'mainfont=PingFang SC', '-V', 'lang=zh', '-V', 'title=A Struggle With Sin 中文攻略', '-o', str(typ))
    import typst
    # 资源相对根使用暂存目录，与网站引用一致。
    typst.compile(str(typ), output=str(output / 'walkthrough-zh.pdf'), root=str(ROOT), font_paths=['/System/Library/Fonts'],)
    print('已按入口顺序导出 %d 章：dist/pdf/walkthrough-zh.pdf' % len(documents))


def main():
    parser = argparse.ArgumentParser(description='中文攻略工程命令')
    parser.add_argument('command', choices=['extract', 'pending', 'assemble', 'sync-readme', 'sync-homepage', 'preview', 'build', 'check', 'pdf'])
    args = parser.parse_args()
    try:
        if args.command == 'sync-readme':
            sync_readme()
        elif args.command == 'sync-homepage':
            sync_homepage()
        elif args.command in ['extract', 'pending', 'assemble', 'check', 'pdf']:
            globals()[args.command]()
        else:
            stage()
            if args.command == 'build':
                run(sys.executable, '-m', 'mkdocs', 'build', '--strict')
                check()
            else:
                run(sys.executable, '-m', 'mkdocs', 'serve', '--dev-addr=127.0.0.1:8000', '--watch=docs', '--watch=glossary.md')
    except KeyboardInterrupt:
        print('预览已停止。')
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print('操作未完成：' + str(error), file=sys.stderr)
        sys.exit(1)
