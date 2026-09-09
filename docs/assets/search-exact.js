(function () {
  'use strict';

  var indexPromise;
  var script = document.currentScript;

  function toHalfWidth(value) {
    return value.replace(/[\uff01-\uff5e]/g, function (character) {
      return String.fromCharCode(character.charCodeAt(0) - 65248);
    }).replace(/\u3000/g, ' ');
  }

  function plainText(value) {
    return value.replace(/<[^>]*>/g, ' ').replace(/\u200b/g, ' ')
      .replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
  }

  function normalize(value) {
    return toHalfWidth(plainText(String(value))).toLowerCase();
  }

  function escapeHtml(value) {
    return value.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function makeSnippet(text, query) {
    var position = normalize(text).indexOf(query);
    var start = Math.max(0, position - 52);
    var end = Math.min(text.length, position + query.length + 118);
    var before = escapeHtml(text.slice(start, position));
    var matched = escapeHtml(text.slice(position, position + query.length));
    var after = escapeHtml(text.slice(position + query.length, end));
    return (start ? '…' : '') + before + '<mark>' + matched + '</mark>' + after + (end < text.length ? '…' : '');
  }

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(new URL('../search/search_exact_index.json', script.src).href)
        .then(function (response) {
          if (!response.ok) {
            throw new Error('无法读取站内搜索索引');
          }
          return response.json();
        })
        .then(function (data) {
          return data.entries.map(function (entry) {
            return {
              location: entry.location,
              pageTitle: plainText(entry.page_title || ''),
              sectionTitle: plainText(entry.section_title || ''),
              text: plainText(entry.text || '')
            };
          });
        });
    }
    return indexPromise;
  }

  function render(meta, list, documents, rawQuery) {
    var query = normalize(rawQuery);
    var matches;
    meta.textContent = query ? '正在搜索…' : '键入以开始搜索';
    list.innerHTML = '';
    if (!query) {
      return;
    }

    matches = documents.map(function (document, order) {
      var pageTitle = normalize(document.pageTitle);
      var sectionTitle = normalize(document.sectionTitle);
      var text = normalize(document.text);
      var textPosition = text.indexOf(query);
      if (textPosition === -1) {
        return null;
      }
      return {
        document: document,
        pageTitlePosition: pageTitle.indexOf(query),
        sectionTitlePosition: sectionTitle.indexOf(query),
        textPosition: textPosition,
        order: order
      };
    }).filter(function (match) {
      return match !== null;
    }).sort(function (left, right) {
      var leftScore = (left.pageTitlePosition === -1 ? 0 : 100000) +
        (left.sectionTitlePosition === -1 ? 0 : 10000);
      var rightScore = (right.pageTitlePosition === -1 ? 0 : 100000) +
        (right.sectionTitlePosition === -1 ? 0 : 10000);
      return rightScore - leftScore || left.order - right.order;
    });

    if (!matches.length) {
      meta.textContent = '没有找到包含“' + rawQuery + '”的结果';
      return;
    }

    meta.textContent = matches.length + ' 个可直接定位的结果';
    matches.slice(0, 30).forEach(function (match) {
      var item = document.createElement('li');
      var link = document.createElement('a');
      var article = document.createElement('article');
      var heading = document.createElement('h2');
      var excerpt = document.createElement('p');
      var title = match.document.pageTitle;

      if (match.document.sectionTitle &&
          normalize(title).indexOf(normalize(match.document.sectionTitle)) === -1) {
        title += ' · ' + match.document.sectionTitle;
      }

      item.className = 'md-search-result__item';
      link.className = 'md-search-result__link';
      link.href = new URL(match.document.location, new URL('../', script.src)).href
        .replace('#', '?exact=' + encodeURIComponent(rawQuery) + '#');
      article.className = 'md-search-result__article md-typeset';
      heading.textContent = title;
      excerpt.innerHTML = makeSnippet(match.document.text, query);
      article.appendChild(heading);
      article.appendChild(excerpt);
      link.appendChild(article);
      item.appendChild(link);
      list.appendChild(item);
    });
  }

  function highlightTarget() {
    var query = location.search.match(/[?&]exact=([^&]*)/);
    var target;
    if (!query || !location.hash) {
      return;
    }
    target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!target) {
      return;
    }
    target.className += (target.className ? ' ' : '') + 'search-target--active';
    window.setTimeout(function () {
      target.className = target.className.replace(/(?:^|\s)search-target--active(?=\s|$)/, '');
    }, 3000);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, document.title, location.pathname + location.hash);
    }
  }

  function initialize() {
    var input = document.querySelector('[data-md-component="search-query"]');
    var result = document.querySelector('[data-md-component="search-result"]');
    var meta;
    var list;
    var timer;

    if (!input || !result) {
      return;
    }
    meta = result.querySelector('.md-search-result__meta');
    list = result.querySelector('.md-search-result__list');

    function search() {
      var query = input.value;
      clearTimeout(timer);
      timer = setTimeout(function () {
        loadIndex().then(function (documents) {
          render(meta, list, documents, query);
        }).catch(function () {
          meta.textContent = '搜索索引加载失败';
          list.innerHTML = '';
        });
      }, 80);
    }

    function intercept(event) {
      if (event.target === input) {
        event.stopImmediatePropagation();
        search();
      }
    }

    document.addEventListener('input', intercept, true);
    document.addEventListener('keyup', intercept, true);
    input.form.addEventListener('reset', function () {
      window.setTimeout(search, 0);
    });
    loadIndex();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initialize();
      highlightTarget();
    });
  } else {
    initialize();
    highlightTarget();
  }
}());
