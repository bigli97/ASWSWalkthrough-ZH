(function () {
  'use strict';

  var root = new URL('../', document.currentScript.src);
  var storageKey = 'guide-search:' + root.pathname;
  var state = { query: '', selected: '', scroll: 0, limit: 30 };
  var entries = [];
  var ready = false;
  var opened = false;
  var lastFocus;
  var readingScroll = 0;
  var targetBlock;
  var navigationVersion = 0;
  var input, list, meta, more, panel, trigger, toolbar;

  function normalize(value) {
    return String(value).replace(/[\uff01-\uff5e]/g, function (character) {
      return String.fromCharCode(character.charCodeAt(0) - 65248);
    }).replace(/\u3000/g, ' ').toLowerCase();
  }

  function terms() {
    return normalize(state.query).trim().split(/\s+/).filter(Boolean);
  }

  function escapeHtml(value) {
    return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function marked(text) {
    var ranges = [];
    var normalized = normalize(text);
    terms().forEach(function (term) {
      var position = normalized.indexOf(term);
      while (position !== -1) {
        ranges.push([position, position + term.length]);
        position = normalized.indexOf(term, position + term.length);
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    ranges.forEach(function (range) {
      var previous = merged[merged.length - 1];
      if (previous && range[0] <= previous[1]) {
        previous[1] = Math.max(previous[1], range[1]);
      } else {
        merged.push(range);
      }
    });
    var result = '', offset = 0;
    merged.forEach(function (range) {
      result += escapeHtml(text.slice(offset, range[0])) + '<mark data-guide-mark="true">' +
        escapeHtml(text.slice(range[0], range[1])) + '</mark>';
      offset = range[1];
    });
    return result + escapeHtml(text.slice(offset));
  }

  function save() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(state)); } catch (error) { /* 禁用存储时仍可搜索。 */ }
  }

  function matches() {
    var words = terms();
    if (!words.length) { return []; }
    return entries.filter(function (entry) {
      return words.every(function (word) {
        return entry.normalized.indexOf(word) !== -1;
      });
    }).sort(function (left, right) {
      function score(entry) {
        return words.filter(function (word) {
          return normalize(entry.page_title + ' ' + entry.section_title).indexOf(word) !== -1;
        }).length;
      }
      return score(right) - score(left) || left.order - right.order;
    });
  }

  function resultUrl(entry) {
    var url = new URL(entry.location, root);
    url.searchParams.set('exact', state.query);
    return url;
  }

  function render(restoreScroll) {
    if (!ready || !opened) { return; }
    var results = matches();
    list.innerHTML = '';
    meta.textContent = terms().length ? (results.length ? '共 ' + results.length + ' 个结果，已展示 ' +
      Math.min(state.limit, results.length) + ' 个' : '没有找到结果，请试试其他关键词') :
      '输入完整关键词；多个关键词用空格分隔';
    results.slice(0, state.limit).forEach(function (entry) {
      var item = document.createElement('li');
      var link = document.createElement('a');
      var heading = [entry.page_title, entry.section_title, entry.step_label].filter(Boolean).join(' › ');
      link.href = resultUrl(entry).href;
      link.className = 'guide-search-link';
      if (state.selected === entry.location) { link.setAttribute('aria-current', 'true'); }
      link.innerHTML = '<strong>' + escapeHtml(heading) + '</strong>' +
        (entry.parent_text ? '<small>' + escapeHtml(entry.parent_text) + '</small>' : '') +
        '<span>' + marked(entry.text) + '</span>';
      link.addEventListener('click', function (event) {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
        state.selected = entry.location;
        state.scroll = list.scrollTop;
        save();
        var url = resultUrl(entry);
        if (url.pathname === location.pathname) {
          event.preventDefault();
          history.pushState({ guideSearchOpen: false }, '', url.href);
          close();
          locate();
          if (opened) { render(true); }
        }
      });
      item.appendChild(link);
      var context = document.createElement('details');
      var summary = document.createElement('summary');
      summary.textContent = '查看前后文';
      context.appendChild(summary);
      [entry.parent_text, entry.before, entry.after].forEach(function (text, index) {
        if (!text) { return; }
        var paragraph = document.createElement('p');
        paragraph.innerHTML = '<b>' + ['所属步骤：', '前文：', '后文：'][index] + '</b>' + marked(text);
        context.appendChild(paragraph);
      });
      item.appendChild(context);
      list.appendChild(item);
    });
    more.hidden = state.limit >= results.length;
    list.scrollTop = restoreScroll ? state.scroll : 0;
  }

  function rememberPanel(value) {
    var data = Object.assign({}, history.state || {});
    data.guideSearchOpen = value;
    history.replaceState(data, '', location.href);
  }

  function open(focusInput) {
    if (!opened) {
      readingScroll = window.scrollY;
      lastFocus = document.activeElement;
    }
    opened = true;
    rememberPanel(true);
    panel.hidden = false;
    document.body.classList.add('guide-search-open');
    input.setAttribute('aria-expanded', 'true');
    render(true);
    if (focusInput !== false) { input.focus({ preventScroll: true }); }
  }

  function close() {
    state.scroll = list.scrollTop;
    save();
    opened = false;
    rememberPanel(false);
    panel.hidden = true;
    save();
    document.body.classList.remove('guide-search-open');
    input.setAttribute('aria-expanded', 'false');
    if (window.matchMedia('(max-width: 999px)').matches) {
      var previousScroll = readingScroll;
      requestAnimationFrame(function () { window.scrollTo({ top: previousScroll, behavior: 'instant' }); });
    }
    if (lastFocus && lastFocus !== input && lastFocus.isConnected) {
      lastFocus.focus({ preventScroll: true });
    }
  }

  function clearHighlights() {
    document.querySelectorAll('mark[data-guide-body-mark]').forEach(function (mark) {
      mark.replaceWith(document.createTextNode(mark.textContent));
    });
    document.querySelectorAll('.guide-search-target').forEach(function (block) {
      block.classList.remove('guide-search-target');
      block.normalize();
    });
  }

  function locate() {
    var version = ++navigationVersion;
    var url = new URL(location.href);
    clearHighlights();
    targetBlock = null;
    toolbar.hidden = true;
    if (!url.searchParams.has('exact') || !url.hash) { return; }
    var anchor;
    try { anchor = document.getElementById(decodeURIComponent(url.hash.slice(1))); } catch (error) { return; }
    if (!anchor) { return; }
    state.query = url.searchParams.get('exact');
    input.value = state.query;
    targetBlock = anchor.closest('[data-search-block]') || anchor;
    targetBlock.classList.add('guide-search-target');
    var walker = document.createTreeWalker(targetBlock, NodeFilter.SHOW_TEXT);
    var nodes = [], node;
    while ((node = walker.nextNode())) {
      if (!node.parentElement.closest('script, style') &&
          (node.parentElement.closest('[data-search-block]') === targetBlock || !targetBlock.hasAttribute('data-search-block'))) {
        nodes.push(node);
      }
    }
    nodes.forEach(function (textNode) {
      var html = marked(textNode.nodeValue);
      if (html.indexOf('<mark') === -1) { return; }
      var template = document.createElement('template');
      template.innerHTML = html;
      template.content.querySelectorAll('mark').forEach(function (mark) {
        mark.setAttribute('data-guide-body-mark', 'true');
      });
      textNode.replaceWith(template.content);
    });
    state.selected = location.pathname.slice(root.pathname.length) + location.hash;
    save();
    function scroll() {
      if (version !== navigationVersion || !targetBlock) { return; }
      targetBlock.scrollIntoView({ block: 'start', behavior: 'instant' });
    }
    requestAnimationFrame(scroll);
    // 上方图片尚未加载时校正位置；用户开始阅读或操作后停止校正。
    var stopped = false;
    var stopEvents = ['wheel', 'touchstart', 'pointerdown', 'keydown'];
    function stop() {
      stopped = true;
      stopEvents.forEach(function (name) { window.removeEventListener(name, stop); });
    }
    stopEvents.forEach(function (name) { window.addEventListener(name, stop, { once: true, passive: true }); });
    document.querySelectorAll('.md-content img').forEach(function (img) {
      if (!img.complete && (img.compareDocumentPosition(targetBlock) & Node.DOCUMENT_POSITION_FOLLOWING)) {
        img.addEventListener('load', function () { if (!stopped) { scroll(); } }, { once: true });
      }
    });
    window.setTimeout(stop, 8000);
    updateToolbar();
  }

  function restoreNavigation() {
    var searchState = Object.assign({}, state);
    locate();
    if (history.state && history.state.guideSearchOpen) {
      state = searchState;
      input.value = state.query;
      save();
      open(false);
    } else if (opened) {
      close();
    }
  }

  function updateToolbar() {
    if (!ready || !targetBlock) { return; }
    var local = matches().filter(function (entry) {
      return new URL(entry.location, root).pathname === location.pathname;
    });
    var index = local.findIndex(function (entry) { return entry.location === state.selected; });
    toolbar.hidden = false;
    toolbar.setAttribute('data-single', local.length <= 1 ? 'true' : 'false');
    toolbar.querySelector('span').textContent = '本章命中 ' + (index + 1) + ' / ' + local.length;
    ['previous', 'next'].forEach(function (direction) {
      var link = toolbar.querySelector('[data-direction="' + direction + '"]');
      var entry = local[index + (direction === 'previous' ? -1 : 1)];
      link.hidden = !entry;
      if (entry) { link.href = resultUrl(entry).href; }
    });
  }

  function initialize() {
    try {
      var stored = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
      if (stored && typeof stored.query === 'string') {
        state.query = stored.query;
        state.selected = typeof stored.selected === 'string' ? stored.selected : '';
        state.scroll = Number(stored.scroll) || 0;
        state.limit = Math.max(30, Number(stored.limit) || 30);
      }
    } catch (error) { /* 忽略不可用的本地状态。 */ }
    trigger = document.createElement('div');
    trigger.className = 'guide-search-trigger';
    trigger.innerHTML = '<input id="guide-query" type="search" placeholder="搜索攻略" autocomplete="off" ' +
      'aria-label="搜索攻略" aria-controls="guide-search" aria-expanded="false">';
    document.querySelector('.md-header__inner').appendChild(trigger);
    panel = document.createElement('section');
    panel.id = 'guide-search';
    panel.className = 'guide-search';
    panel.hidden = true;
    panel.setAttribute('aria-label', '搜索攻略');
    panel.innerHTML = '<div class="guide-search-summary"><p class="guide-search-meta" role="status">正在加载搜索索引…</p>' +
      '<button type="button" data-close>收起</button></div><ol class="guide-search-results"></ol>' +
      '<button type="button" data-more hidden>再显示 30 条</button>';
    document.body.appendChild(panel);
    input = trigger.querySelector('input');
    list = panel.querySelector('ol');
    meta = panel.querySelector('[role="status"]');
    more = panel.querySelector('[data-more]');
    input.value = state.query;
    input.addEventListener('focus', function () { open(false); });
    panel.querySelector('[data-close]').addEventListener('click', close);
    document.addEventListener('pointerdown', function (event) {
      if (opened && window.matchMedia('(min-width: 1000px)').matches &&
          !panel.contains(event.target) && !trigger.contains(event.target)) { close(); }
    });
    input.addEventListener('input', function (event) {
      if (event.isComposing) { return; }
      if (!opened) { open(false); }
      state.query = input.value; state.scroll = 0; state.limit = 30; save(); render(false);
    });
    input.addEventListener('compositionend', function () {
      state.query = input.value; state.scroll = 0; state.limit = 30; save(); render(false);
    });
    more.addEventListener('click', function () {
      state.scroll = list.scrollTop; state.limit += 30; save(); render(true);
    });
    list.addEventListener('scroll', function () { state.scroll = list.scrollTop; save(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && opened) { close(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); open(); }
    });
    toolbar = document.createElement('nav');
    toolbar.className = 'guide-search-toolbar';
    toolbar.setAttribute('aria-label', '搜索定位');
    toolbar.hidden = true;
    toolbar.innerHTML = '<button type="button">返回搜索结果</button><span></span>' +
      '<a data-direction="previous">上一处</a><a data-direction="next">下一处</a>';
    document.querySelector('.md-main').prepend(toolbar);
    toolbar.querySelector('button').addEventListener('click', function () { open(); });
    toolbar.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
        event.preventDefault(); history.pushState({ guideSearchOpen: opened }, '', link.href); locate();
        if (opened) { render(true); }
      });
    });
    window.addEventListener('hashchange', restoreNavigation);
    window.addEventListener('popstate', restoreNavigation);
    window.addEventListener('pageshow', function (event) {
      if (event.persisted) {
        try {
          var latest = JSON.parse(sessionStorage.getItem(storageKey));
          if (latest) { state = latest; input.value = state.query; }
        } catch (error) { /* 保留内存中的搜索状态。 */ }
        restoreNavigation();
      }
    });
    restoreNavigation();
    fetch(new URL('search/search_exact_index.json', root).href).then(function (response) {
      if (!response.ok) { throw new Error('索引加载失败'); }
      return response.json();
    }).then(function (data) {
      entries = data.entries.map(function (entry, order) {
        entry.order = order;
        entry.normalized = normalize(entry.text);
        return entry;
      });
      ready = true;
      render(true);
      updateToolbar();
    }).catch(function () { meta.textContent = '搜索索引加载失败，请刷新页面重试'; });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initialize); }
  else { initialize(); }
}());
