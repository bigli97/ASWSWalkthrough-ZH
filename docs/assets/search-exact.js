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

  function countMatches(text, query) {
    var count = 0;
    var start = 0;
    while (text.indexOf(query, start) !== -1) {
      count += 1;
      start = text.indexOf(query, start) + query.length;
    }
    return count;
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
      indexPromise = fetch(new URL('../search/search_index.json', script.src).href)
        .then(function (response) {
          if (!response.ok) {
            throw new Error('无法读取站内搜索索引');
          }
          return response.json();
        })
        .then(function (data) {
          return data.docs.map(function (document) {
            return {
              location: document.location,
              title: plainText(document.title || ''),
              text: plainText(document.text || '')
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

    matches = documents.map(function (document) {
      var title = normalize(document.title);
      var text = normalize(document.text);
      var titlePosition = title.indexOf(query);
      var textPosition = text.indexOf(query);
      if (titlePosition === -1 && textPosition === -1) {
        return null;
      }
      return {
        document: document,
        titlePosition: titlePosition,
        textPosition: textPosition,
        count: countMatches(title, query) + countMatches(text, query)
      };
    }).filter(function (match) {
      return match !== null;
    }).sort(function (left, right) {
      var leftScore = (left.titlePosition === -1 ? 0 : 100000) + left.count * 100 - Math.max(left.titlePosition, 0);
      var rightScore = (right.titlePosition === -1 ? 0 : 100000) + right.count * 100 - Math.max(right.titlePosition, 0);
      return rightScore - leftScore;
    });

    if (!matches.length) {
      meta.textContent = '没有找到包含“' + rawQuery + '”的结果';
      return;
    }

    meta.textContent = matches.length + ' 个包含完整输入内容的结果';
    matches.slice(0, 30).forEach(function (match) {
      var item = document.createElement('li');
      var link = document.createElement('a');
      var article = document.createElement('article');
      var heading = document.createElement('h2');
      var excerpt = document.createElement('p');
      var source = match.titlePosition !== -1 ? match.document.title : match.document.text;

      item.className = 'md-search-result__item';
      link.className = 'md-search-result__link';
      link.href = new URL(match.document.location, new URL('../', script.src)).href;
      article.className = 'md-search-result__article md-typeset';
      heading.textContent = match.document.title;
      excerpt.innerHTML = makeSnippet(source, query);
      article.appendChild(heading);
      article.appendChild(excerpt);
      link.appendChild(article);
      item.appendChild(link);
      list.appendChild(item);
    });
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
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }
}());
