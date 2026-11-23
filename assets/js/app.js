/* 羊毛情报局 — interaction layer
   1. 单开手风琴（手机端整卡可点）              2. 搜索 / 筛选 / 排序（读 JSON 索引）
   3. 分类内左右横滑翻页（手机 5 张/页 · 桌面 8 张/页） 4. 热榜板 tab（桌面双板 / 手机单板）
   5. 右侧竖版滑轨高亮（桌面 + 手机）            6. 图标兜底
   7. 跳转卡落到分类详情（自动翻到所在页）       8. 筛选状态同步到 URL
   静态卡片已在 HTML 里，脚本只做增强，禁用 JS 也能正常阅读。 */
(function () {
  "use strict";

  document.documentElement.classList.add("js");

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var PAGE_SIZE = 5;            // 手机端分类卡一页 5 条
  var PAGE_SIZE_LG = 8;         // 桌面端双列网格一页 8 条
  var TODAY_WINDOW_DAYS = 2;    // 与 scripts/common.py 的 TODAY_WINDOW_DAYS 保持一致
  var mqMobile = window.matchMedia("(max-width: 768px)");
  /* 系统开了「减少动态效果」就不滚动动画：滚动仍到位，只是不滑。 */
  var mqReduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  function scrollBehavior() { return mqReduce.matches ? "auto" : "smooth"; }

  /* ------------------------------------------------------------ favicons */
  /* 图标已在构建时缓存到 assets/fav/，加载失败就退回首字母块，不再请求第三方。 */
  window.__favFallback = function (img) {
    img.style.display = "none";
    var fb = img.nextElementSibling;
    if (fb && fb.classList.contains("fav-fallback")) fb.style.display = "grid";
  };

  $$(".fav").forEach(function (img) {
    if (img.complete && img.naturalWidth === 0) window.__favFallback(img);
  });

  /* ------------------------------------------------------------ Cookie 同意 */
  /* 面板、localStorage 与 window.__dhConsent 都在 /assets/js/consent.js（全站共用，含
     详情 / 分类 / 合规页）。首页这份交互脚本只在同意变化后通知按需加载的模块：
     以后接 GA4 / AdSense 时实现 window.__dhOnConsent = function (state) {…} 即可，
     不用在页面其它地方再判断一次。 */
  document.addEventListener("dh:consent-changed", function (ev) {
    if (typeof window.__dhOnConsent === "function") window.__dhOnConsent(ev.detail);
  });

  /* ------------------------------------------------------- 语言（中文 / English）*/
  /* 页面是单语的：/ 只有中文、/en/ 只有英文，DOM 里没有成对的中英节点。
     LANG 只用于 JS 自己生成的少量文案（aria-label、提交表单的 lang 字段）；
     切换语言是整页跳转（/ ↔ /en/），保留 #hash 与 ?q= 等参数。 */
  var IS_EN_PAGE = /^\/en(\/|$)/.test(location.pathname);
  var LANG = document.documentElement.getAttribute("data-lang") === "en" ? "en" : "zh";

  /* 另一语言版本的地址：同一套查询参数（去掉 lang）+ 当前 hash */
  function otherLangHref() {
    var params = new URLSearchParams(location.search);
    params.delete("lang");
    var qs = params.toString();
    return (IS_EN_PAGE ? "/" : "/en/") + (qs ? "?" + qs : "") + (location.hash || "");
  }

  /* ------------------------------------------------------- 搜索索引（JSON） */
  /* 首页只内联每类前 25 条（Hark 第七轮定稿的瘦身口径），索引因此只带四部分：
       h 检索词 · c 分类词表（按分类只存一次）· t 标题（只给未内联的在效条目）·
       p 未内联条目：搜到时补一行轻量卡，点进它的 /d/<id>/ 独立页。
     内联卡片的标题直接从 DOM 的 h3 上取，不在索引里再存一份。
     旧格式（{id: 文本} 或 {zh:…, en:…}）也还能读。 */
  var SEARCH = {};
  var TITLES = {};
  var POOL = {};
  var CATQ = {};
  var RAW_HAY = {};
  var OLD_FLAT = null;
  var indexEl = $("#search-index");
  if (indexEl) {
    var rawIndex = null;
    try { rawIndex = JSON.parse(indexEl.textContent) || {}; } catch (err) { rawIndex = null; }
    if (rawIndex) {
      var legacy = rawIndex.zh || rawIndex.en ? (rawIndex[LANG] || rawIndex.zh || {}) : null;
      if (rawIndex.h) {
        CATQ = rawIndex.c || {};
        RAW_HAY = rawIndex.h;
        TITLES = rawIndex.t || {};
        POOL = rawIndex.p || {};
        // 旧版带 k（条目分类）的索引：这里只记下来，下面拼检索串时补进去
        var kMap = rawIndex.k || {};
        Object.keys(kMap).forEach(function (id) {
          if (RAW_HAY[id] !== undefined) RAW_HAY[id] += " " + (CATQ[kMap[id]] || "");
        });
      } else if (legacy) {
        OLD_FLAT = legacy;
      } else {
        OLD_FLAT = rawIndex;
      }
    }
  }

  /* 拼检索串：标题（未内联的来自索引，内联的取自卡片 h3）+ 其余检索词 + 分类词表。
     在 modules 建好后跑一次（内联卡片的 h3 那时已经在 DOM 里）。 */
  function buildSearch() {
    if (OLD_FLAT) {
      Object.keys(OLD_FLAT).forEach(function (id) { SEARCH[id] = String(OLD_FLAT[id]).toLowerCase(); });
      return;
    }
    function add(id, title, cat) {
      if (!id) return;
      SEARCH[id] = ((title || "") + " " + (SEARCH[id] || "") + " " + (CATQ[cat] || ""))
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
    }
    Object.keys(RAW_HAY).forEach(function (id) { SEARCH[id] = RAW_HAY[id]; });
    Object.keys(POOL).forEach(function (id) { add(id, TITLES[id] || "", POOL[id][0]); });
    modules.forEach(function (m) {
      m.items.forEach(function (card) {
        var h3 = card.querySelector("h3");
        add(card.dataset.key, h3 ? h3.textContent : "", card.dataset.cat);
      });
    });
  }

  /* 未内联条目按分类分好：搜索 / 筛选时直接往对应分区的轨道里补结果行 */
  var POOL_BY_CAT = {};
  Object.keys(POOL).forEach(function (id) {
    var cat = POOL[id][0];
    (POOL_BY_CAT[cat] = POOL_BY_CAT[cat] || []).push(id);
  });
  var DETAIL_BASE = /^\/en(\/|$)/.test(location.pathname) ? "/en/d/" : "/d/";
  var HITS = {};

  /* 一条「首页没内联」的搜索结果行：图标 + 标题 + 价值 / 门槛 / 截止，点进独立详情页。
     字段顺序见 build_site.py 的 search_p：[cat, cost, verified, added_at, end,
     value_exp, fav, monogram, value_text, deadline]。 */
  function hitEl(id) {
    var d = POOL[id];
    if (!d) return null;
    if (HITS[id]) return HITS[id];
    var a = document.createElement("a");
    a.className = "hit";
    a.href = DETAIL_BASE + encodeURIComponent(id) + "/";
    a.dataset.key = id;
    a.dataset.cat = d[0];
    a.dataset.cost = d[1];
    a.dataset.verified = d[2];
    a.dataset.addedAt = d[3];
    a.dataset.added = String(d[3] || "").slice(0, 10);
    a.dataset.end = d[4];
    a.dataset.valExp = d[5];
    if (d[6]) {
      var img = document.createElement("img");
      img.className = "fav";
      img.src = "/assets/fav/" + d[6] + ".webp";
      img.width = 22;
      img.height = 22;
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.onerror = function () { if (window.__favFallback) window.__favFallback(img); };
      a.appendChild(img);
      var fb = document.createElement("span");
      fb.className = "fav-fallback";
      fb.style.display = "none";
      fb.setAttribute("aria-hidden", "true");
      fb.textContent = d[7] || "?";
      a.appendChild(fb);
    } else {
      var letter = document.createElement("span");
      letter.className = "fav-fallback";
      letter.style.display = "grid";
      letter.setAttribute("aria-hidden", "true");
      letter.textContent = d[7] || "?";
      a.appendChild(letter);
    }
    var main = document.createElement("span");
    main.className = "hit-main";
    var title = document.createElement("span");
    title.className = "hit-t";
    title.textContent = TITLES[id] || id;
    var meta = document.createElement("span");
    meta.className = "hit-m";
    meta.textContent = [d[8], d[1], d[9]].filter(Boolean).join(" · ");
    main.appendChild(title);
    main.appendChild(meta);
    var go = document.createElement("span");
    go.className = "hit-go";
    go.setAttribute("aria-hidden", "true");
    go.textContent = "\u2197";
    a.appendChild(main);
    a.appendChild(go);
    HITS[id] = a;
    return a;
  }

  /* 有没有在搜索 / 筛：只有这种时候才把未内联的条目补成结果行，
     平时首页就是每类那 25 条，不为全库铺 DOM。 */
  function isFiltering() {
    return !!(state.q || state.time !== "all" || state.cat !== "all"
              || state.cost !== "all" || state.verify !== "all");
  }

  /* ------------------------------------------------------------- modules */
  var modules = $$(".module").map(function (sec) {
    return {
      el: sec,
      anchor: sec.id,
      isJump: sec.dataset.kind === "jump",
      track: $("[data-track]", sec),
      bar: $("[data-bar]", sec),
      label: $("[data-label]", sec),
      countEl: $("[data-count]", sec),
      empty: $(".module-empty", sec),
      more: $("[data-more]", sec),
      per: parseInt(sec.dataset.per, 10) || PAGE_SIZE,
      perLg: parseInt(sec.dataset.perLg, 10) || PAGE_SIZE_LG,
      items: $$(sec.dataset.kind === "jump" ? ".jump" : ".card", sec),
      total: 0
    };
  });

  /* 记下每张卡在 build_site.py 里的顺序 = score_deal 的顺序（AI 综合打分 + KYC 沉底 +
     多样性护栏）。切回「综合推荐」时按这个索引还原，绝不拿 valExp 重排。 */
  modules.forEach(function (m) {
    m.items.forEach(function (el, idx) { el.dataset.buildIdx = String(idx); });
  });

  /* 检索串要等 modules 建好再拼：内联卡片的标题从卡上的 h3 取，不占索引体积 */
  buildSearch();

  /* 板子 tab 上的条数、顶部「匹配 N 条」都是静态节点：初始化时查一次表，
     以后 render 直接改文字，不要再对整个 1.9 MB 文档做 querySelectorAll。 */
  var TABCOUNT = {};
  $$("[data-tabcount]").forEach(function (el) {
    var k = el.getAttribute("data-tabcount");
    (TABCOUNT[k] = TABCOUNT[k] || []).push(el);
  });
  var RESULT_ELS = $$("[data-result]");

  /* --------------------------------------------------------------- state */
  var state = { q: "", time: "all", cat: "all", cost: "all", verify: "all", sort: "value" };

  /* 「今天」必须按北京时间算：数据里的 added / end 都是北京时间日期，
     英文版主要受众在美国，用浏览器本地零点会把 24h / 48h 筛差一天。
     构建时把北京日期写进 <html data-today>，这里只做解析；拿不到才退回本地日期。 */
  var TODAY = (function () {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(document.documentElement.getAttribute("data-today") || "");
    var d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  })();
  var DAY = 86400000;

  function cardDate(card, key) {
    var v = card.dataset[key];
    if (!v) return null;
    var d = new Date(v + "T00:00:00");
    return isNaN(d.getTime()) ? null : d;
  }

  function matches(card) {
    if (state.cat !== "all" && card.dataset.cat !== state.cat) return false;
    if (state.cost !== "all" && card.dataset.cost !== state.cost) return false;
    if (state.verify !== "all" && card.dataset.verified !== state.verify) return false;

    if (state.q) {
      var hay = (SEARCH[card.dataset.key] || "") + " " + (card.dataset.cat || "");
      var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var i = 0; i < terms.length; i++) {
        if (hay.indexOf(terms[i]) === -1) return false;   // 空格分词，全部命中才算
      }
    }

    var end = cardDate(card, "end");
    /* 「近 24 / 48 小时 / 7 天」是滑动窗口，不是自然日：
       拿卡片上的 added_at 完整时间戳（带时区）和当前时刻比，
       不能拿「今天零点 − 收录日期」比——那样 24 小时会变成今天+昨天两天。 */
    if (state.time === "all") return true;   /* 默认不筛时间：省掉每张卡的日期解析 */
    var addedMs = addedTime(card);
    var nowMs = Date.now();

    if (state.time === "24h") {
      if (addedMs == null || nowMs - addedMs > DAY) return false;
    } else if (state.time === "48h") {
      if (addedMs == null || nowMs - addedMs > DAY * TODAY_WINDOW_DAYS) return false;
    } else if (state.time === "7d") {
      if (addedMs == null || nowMs - addedMs > DAY * 7) return false;
    } else if (state.time === "past") {
      var isOld = addedMs != null && nowMs - addedMs > DAY * 7;
      var isOver = end && end < TODAY;
      if (!isOld && !isOver) return false;
    }
    return true;
  }

  /* 入库时刻（毫秒）：优先 data-added-at 的完整时间戳，拿不到再退回日期零点。 */
  function addedTime(card) {
    var raw = card.dataset.addedAt || "";
    if (raw) {
      var t = Date.parse(raw);
      if (!isNaN(t)) return t;
    }
    var d = cardDate(card, "added");
    return d ? d.getTime() : null;
  }

  function sortCards(list, anchor) {
    if (anchor === "rank" || anchor === "archive" || anchor === "lottery") return;
    var by = state.sort;
    list.sort(function (a, b) {
      if (by === "new") {
        /* 同一天入库的条目很多，只按日期排会退化成价值序：带时分的时间戳优先。 */
        var na = a.dataset.addedAt || (a.dataset.added || "") + "T00:00:00";
        var nb = b.dataset.addedAt || (b.dataset.added || "") + "T00:00:00";
        return nb.localeCompare(na) ||
               (+b.dataset.valExp || 0) - (+a.dataset.valExp || 0);
      }
      if (by === "end") {
        var ea = a.dataset.end || "9999-12-31";
        var eb = b.dataset.end || "9999-12-31";
        return ea.localeCompare(eb);
      }
      /* 默认「综合推荐」：构建顺序就是 score_deal 的结论（已含 AI 打分、
         门槛/低通过率沉底、同源分散），这里只按构建索引还原，不再按金额覆盖；
         搜索补进来的 .hit 行（没有 buildIdx）排在后面。 */
      var ia = a.dataset.buildIdx === undefined ? 1e9 : +a.dataset.buildIdx;
      var ib = b.dataset.buildIdx === undefined ? 1e9 : +b.dataset.buildIdx;
      return ia - ib;
    });
  }

  /* ------------------------------------------------------------ rendering */
  /* 分类内一律按页切：手机单列一页 5 张（一屏装得下），桌面双列一页 8 张，
     左右横滑 + 页码条翻页；热榜跳转卡不平铺翻页，2 列网格全部展开。 */
  function perOf(m) {
    return mqMobile.matches ? m.per : m.perLg;
  }

  function buildTrack(m, visible, paged) {
    var track = m.track;
    if (!track) return;
    /* 先把整条轨道一次性清空（卡片引用还在 m.items 里），再在离屏 fragment 里拼好新的
       分页结构，最后一次性挂回去：DOM 只改一次，不再每 appendChild 一张卡就让浏览器
       重排整条轨道。scrollLeft 归零交给 render 的读阶段统一做。 */
    track.textContent = "";
    var frag = document.createDocumentFragment();
    if (paged) {
      var per = perOf(m);
      for (var i = 0; i < visible.length; i += per) {
        var page = document.createElement("div");
        page.className = "page";
        visible.slice(i, i + per).forEach(function (el) {
          el.classList.remove("is-extra");
          page.appendChild(el);
        });
        frag.appendChild(page);
      }
    } else {
      visible.forEach(function (el) {
        el.classList.remove("is-extra");
        frag.appendChild(el);
      });
    }
    track.appendChild(frag);
  }

  function pageCount(m) {
    return Math.max(1, Math.ceil(m.total / perOf(m)));
  }

  /* 页码 1 / N 与左右按钮的可用状态，跟着横滑位置走。
     读（clientWidth / scrollLeft 会强制排版）和写分开：render 一次读完全部分区再写，
     整个页面只排一次版；单个分区刷新时 updateBar 两步连着做也一样。 */
  function barState(m) {
    var pages = pageCount(m);
    var show = !m.isJump && m.total > 0 && pages > 1;
    var idx = 0;
    if (show && m.track) {
      var w = m.track.clientWidth || 1;
      idx = Math.min(Math.max(Math.round(m.track.scrollLeft / w), 0), pages - 1);
    }
    return { pages: pages, show: show, idx: idx };
  }

  function applyBar(m, st) {
    m.bar.style.display = st.show ? "flex" : "none";
    if (!st.show) return;
    if (m.label) m.label.textContent = (st.idx + 1) + " / " + st.pages;
    var prev = $("[data-prev]", m.bar);
    var next = $("[data-next]", m.bar);
    if (prev) prev.disabled = st.idx <= 0;
    if (next) next.disabled = st.idx >= st.pages - 1;
  }

  function updateBar(m) {
    if (!m.bar) return;
    applyBar(m, barState(m));
  }

  function render() {
    var seen = {};
    var matchedTotal = 0;
    /* 搜索 / 筛选时把「首页没内联的在效条目」补进来：一行轻量卡，点进独立页。
       平时（默认状态）不补，首页只画每类前 25 条。 */
    var deep = isFiltering();

    modules.forEach(function (m) {
      var visible = m.items.filter(matches);
      if (deep && !m.isJump && m.anchor !== "archive") {
        (POOL_BY_CAT[m.anchor] || []).forEach(function (id) {
          var el = hitEl(id);
          if (el && matches(el)) visible.push(el);
        });
      }
      if (!m.isJump) sortCards(visible, m.anchor);
      m.total = visible.length;

      // 只数分类区里的完整卡：每个 data-key 只算一次，
      // 热榜的跳转卡不参与计数，避免「匹配 N 条」翻倍。
      if (!m.isJump) {
        visible.forEach(function (el) {
          var key = el.dataset.key;
          if (key && seen[key]) return;
          if (key) seen[key] = 1;
          matchedTotal++;
        });
      }

      if (m.countEl) m.countEl.textContent = visible.length;
      (TABCOUNT[m.anchor] || []).forEach(function (el) {
        el.textContent = visible.length;
      });
      if (m.empty) m.empty.style.display = visible.length ? "none" : "block";

      var paged = !m.isJump;
      buildTrack(m, visible, paged);
      if (m.track) m.track.style.display = visible.length ? "" : "none";

      // 桌面端也不再折叠：分类内一律翻页
      m.el.dataset.collapsed = "0";
      if (m.more) m.more.hidden = true;
    });

    RESULT_ELS.forEach(function (el) { el.textContent = matchedTotal; });

    /* 上面全是写：条数、轨道、分页 DOM。翻页条要读 clientWidth / scrollLeft（会强制排版），
       轨道回第 1 页的 scrollLeft 写入同样会逼一次排版——以前每个分区各逼一次，320 张卡的
       整页就排了 11 遍。这里把读和 scrollLeft 都挪到所有分区搭好之后：整页只排一次版。 */
    modules.forEach(function (m) {
      if (m.track) m.track.scrollLeft = 0;
    });
    var barStates = modules.map(function (m) { return m.bar ? barState(m) : null; });
    barStates.forEach(function (st, i) {
      if (st) applyBar(modules[i], st);
    });

    syncNav();
    syncURL();
  }

  /* 分类内左右翻页按钮（手机 / 桌面同一套） */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-prev], [data-next]");
    if (!btn) return;
    var m = modules.filter(function (x) { return x.bar && x.bar.contains(btn); })[0];
    if (!m || !m.track) return;
    ev.preventDefault();
    var dir = btn.hasAttribute("data-prev") ? -1 : 1;
    m.track.scrollBy({ left: dir * m.track.clientWidth, behavior: "smooth" });
    // 平滑滚动期间先按目标页刷新页码，手指直接滑动时再由 scroll 事件接管
    var pages = pageCount(m);
    var idx = Math.min(Math.max(Math.round(m.track.scrollLeft / (m.track.clientWidth || 1)) + dir, 0), pages - 1);
    if (m.label) m.label.textContent = (idx + 1) + " / " + pages;
    clearTimeout(m._tick);
    m._tick = setTimeout(function () { updateBar(m); }, 380);
  });

  document.addEventListener("scroll", function (ev) {
    var track = ev.target;
    if (!track || !track.hasAttribute || !track.hasAttribute("data-track")) return;
    var m = modules.filter(function (x) { return x.track === track; })[0];
    if (!m) return;
    clearTimeout(m._tick);
    m._tick = setTimeout(function () { updateBar(m); }, 80);
  }, true);

  /* ------- 热榜板：桌面左「新收录 / 高价值榜」· 右「即将截止 / 抽奖」，手机合成一块 ------- */
  var hotBoard = $("[data-hot-board]");
  var hotPanels = [];
  var mobileTabs = [];
  var mobileActive = "fresh";

  if (hotBoard) {
    mobileTabs = $$(".hot-tabs-mobile .hot-tab", hotBoard);
    $$(".hot-panel", hotBoard).forEach(function (panel) {
      var tabs = $$(".hot-tab", panel);
      var current = null;
      tabs.forEach(function (t) { if (!current && t.classList.contains("on")) current = t; });
      current = current || tabs[0];
      hotPanels.push({
        el: panel,
        body: $("[data-panel-body]", panel),
        tabs: tabs,
        ids: tabs.map(function (t) { return t.dataset.tab; }),
        active: current ? current.dataset.tab : null
      });
    });
  }

  function panelOf(id) {
    for (var i = 0; i < hotPanels.length; i++) {
      if (hotPanels[i].ids.indexOf(id) >= 0) return hotPanels[i];
    }
    return null;
  }

  function markTab(tab, on) {
    tab.classList.toggle("on", !!on);
    if (on) tab.setAttribute("aria-current", "true");
    else tab.removeAttribute("aria-current");
  }

  /* 手机：4 个 tab 共用一个 active；桌面：两块板各看各的 */
  function applyBoard() {
    var mobile = mqMobile.matches;
    var active = mobile ? mobileActive : null;

    hotPanels.forEach(function (panel) {
      panel.ids.forEach(function (id) {
        var sec = document.getElementById(id);
        if (!sec) return;
        sec.hidden = mobile ? id !== active : id !== panel.active;
      });
      panel.tabs.forEach(function (tab) {
        markTab(tab, mobile ? tab.dataset.tab === active : tab.dataset.tab === panel.active);
      });
    });
    mobileTabs.forEach(function (tab) {
      markTab(tab, mobile ? tab.dataset.tab === active : false);
    });

    /* 首屏防抖（CLS）：构建期 /rank /lottery 已经带 hidden，手机断点下 #closing 由 CSS
       先隐住（html:not(.board-ready)），这里把板子切成终态之后再放开，
       页面就不会在 applyBoard 执行时整块上跳。桌面端两块板本来就这样，不受影响。 */
    document.documentElement.classList.add("board-ready");

    syncNav();
  }

  function showTab(id) {
    if (!panelOf(id)) return false;
    if (mqMobile.matches) mobileActive = id;
    else panelOf(id).active = id;
    applyBoard();
    return true;
  }

  /* 板子已经好好在屏幕里就别滚：点 tab 不该让页面自己动 */
  function scrollToBoard() {
    if (!hotBoard) return;
    var rect = hotBoard.getBoundingClientRect();
    var barH = mqMobile.matches ? 64 : 68;
    if (rect.top >= barH && rect.top <= window.innerHeight - 140) return;
    var top = window.scrollY + rect.top - barH;
    window.scrollTo({ top: Math.max(top, 0), behavior: scrollBehavior() });
  }

  /* 顶部 tab、右侧滑轨里指向热榜的入口都落到同一块板 */
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest) return;
    var link = ev.target.closest(
      '[data-tab], a[href="#fresh"], a[href="#rank"], a[href="#closing"], a[href="#lottery"], a[href="#expiring"]'
    );
    if (!link || link.closest("[data-jump]")) return;
    var id = link.dataset.tab || (link.getAttribute("href") || "").slice(1);
    if (id === "expiring") id = "closing";
    if (!panelOf(id)) return;
    if (!showTab(id)) return;
    ev.preventDefault();
    scrollToBoard();
    if (history.replaceState) history.replaceState(null, "", "#" + id);
  });

  /* ------------------------- 「即将截止」口径吐司：点迷你日历小标弹出，3.5 秒自己走 */
  var closingToast = document.getElementById("closing-toast");
  var closingInfoBtns = $$(".closing-cal");
  var closingToastTimer = null;
  var closingInfoOn = null;

  /* 吐司挂在小日历下方，左右都夹进视口：375px 窄屏也不会挤出横向滚动条；
     万一下方放不下（键盘弹起 / 屏很矮）就翻到按钮上方。 */
  function placeClosingToast(btn) {
    if (!closingToast || !btn) return;
    var r = btn.getBoundingClientRect();
    if (!r.width || r.bottom < 0 || r.top > window.innerHeight) {
      hideClosingToast();
      return;
    }
    var pad = 10;
    var w = closingToast.offsetWidth;
    var h = closingToast.offsetHeight;
    var left = r.left + r.width / 2 - 20;
    left = Math.min(Math.max(left, pad), window.innerWidth - w - pad);
    var top = r.bottom + 8;
    if (top + h > window.innerHeight - pad) top = Math.max(pad, r.top - h - 8);
    closingToast.style.left = Math.round(left) + "px";
    closingToast.style.top = Math.round(top) + "px";
  }

  function hideClosingToast() {
    if (!closingToast || closingToast.hidden) return;
    closingToast.hidden = true;
    clearTimeout(closingToastTimer);
    closingToastTimer = null;
    if (closingInfoOn) {
      closingInfoOn.setAttribute("aria-expanded", "false");
      closingInfoOn = null;
    }
  }

  function showClosingToast(btn) {
    if (!closingToast) return;
    closingToast.hidden = false;
    closingInfoOn = btn;
    btn.setAttribute("aria-expanded", "true");
    placeClosingToast(btn);
    clearTimeout(closingToastTimer);
    closingToastTimer = setTimeout(hideClosingToast, 3500);
  }

  closingInfoBtns.forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      // 小日历在 tab 旁边：别顺带切 tab、也别顺带收起展开的卡片
      ev.preventDefault();
      ev.stopPropagation();
      if (closingInfoOn === btn) hideClosingToast();
      else showClosingToast(btn);
    });
  });

  if (closingToast) {
    window.addEventListener("resize", function () { if (closingInfoOn) placeClosingToast(closingInfoOn); });
    window.addEventListener("scroll", function () {
      if (closingInfoOn) placeClosingToast(closingInfoOn);
    }, { passive: true });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") hideClosingToast();
    });
    // 点空白处关（捕获阶段先看一眼：点在 ⓘ / 吐司本身就别关）
    document.addEventListener("click", function (ev) {
      if (!closingInfoOn) return;
      if (ev.target.closest && ev.target.closest(".closing-cal, #closing-toast")) return;
      hideClosingToast();
    }, true);
  }

  /* ------------------------------------------------------------ accordion */
  function setOpen(card, open) {
    card.classList.toggle("open", open);
    var toggle = $(".toggle", card);
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", LANG === "en"
        ? (open ? "Collapse details" : "Expand details")
        : (open ? "收起详情" : "展开详情"));
    }
  }

  function closeAll(except) {
    $$(".card.open").forEach(function (card) {
      if (card !== except) setOpen(card, false);
    });
  }

  function openCard(card) {
    closeAll(card);
    setOpen(card, true);
    syncNav();
  }

  /* 点卡片头部或「详情」按钮开合；手机端整张卡都能点开 */
  document.addEventListener("click", function (ev) {
    var card = ev.target.closest(".card");
    if (!card) return;
    if (ev.target.closest(".go") || ev.target.closest(".url-link") || ev.target.closest(".dlink")) return; // 直达链接 / 详情页链接不触发折叠
    if (ev.target.closest(".cf-btn") || ev.target.closest(".cf-sheet") || cfLocked()) return; // 优惠内容按钮 / 吐司不触发折叠
    var head = ev.target.closest(".card-head");
    var toggle = ev.target.closest(".toggle");
    if (!head && !toggle) {
      // 手机端：没有「详情」按钮了，点卡片任意位置就展开（收起仍走头部，避免误触）
      if (!(mqMobile.matches && !card.classList.contains("open"))) return;
    }
    ev.preventDefault();
    if (card.classList.contains("open")) setOpen(card, false);
    else openCard(card);
  });

  /* 把某张卡带到视野中央：先横向翻到它所在的那一页（手机 / 桌面） */
  function revealDeal(target, behavior, offset) {
    var track = target.closest("[data-track]");
    var page = target.closest(".page");
    if (track && page) {
      track.scrollLeft = page.offsetLeft;
      var m = modules.filter(function (x) { return x.track === track; })[0];
      if (m) updateBar(m);
    }
    var rect = target.getBoundingClientRect();
    var top = window.scrollY + rect.top - (offset == null ? 80 : offset);
    window.scrollTo({ top: Math.max(top, 0), behavior: behavior || "auto" });
  }

  /* 跳转卡：翻到卡片所在页、滚到它并展开 */
  document.addEventListener("click", function (ev) {
    var jump = ev.target.closest("[data-jump]");
    if (!jump) return;
    var key = jump.dataset.jump;
    var target = document.getElementById(key);
    if (!target) return;
    ev.preventDefault();

    openCard(target);
    revealDeal(target, scrollBehavior(), 90);
    target.classList.remove("flash");
    void target.offsetWidth;
    target.classList.add("flash");
    if (history.replaceState) history.replaceState(null, "", "#" + key);
  });

  /* 点空白处（卡片与跳转卡之外）收起已展开的卡片 */
  document.addEventListener("click", function (ev) {
    if (ev.target.closest && ev.target.closest(".card.open")) return;
    if (ev.target.closest && ev.target.closest("[data-jump]")) return;
    if (ev.target.closest && ev.target.closest(".modal.on")) return;
    if (ev.target.closest && ev.target.closest(".cf-sheet")) return; // 点吐司（含遮罩）只收吐司，不折叠卡片
    if (cfLocked()) return;  // 吐司刚收起的那一次点击不再连锁收起卡片
    closeAll(null);
  });

  /* ------------------------------------------------------------ 滑轨高亮 */
  var navLinks = $$(".rail a[data-target]");
  var sections = $$(".module");
  /* 聚合看板里的四块板（新收录 / 高价值榜 / 即将截止 / 抽奖）在滑轨里只有一格 */
  var BOARD_TARGET = { fresh: 1, rank: 1, closing: 1, lottery: 1 };
  var navRaf = null;
  /* 点击滑轨后页面还要平滑滚一段：这段时间把高亮钉在刚点的分区，
     不要让高亮跟着中间分区一个个扫过去（那就是用户看到的「过渡延迟」） */
  var navJumpUntil = 0;

  function syncNav() {
    if (!navLinks.length) return;
    if (performance.now() < navJumpUntil) return;
    var probe = window.scrollY + (mqMobile.matches ? 72 : 76);
    var visible = sections.filter(function (sec) { return !sec.hidden; });
    if (!visible.length) return;
    var current = null;
    visible.forEach(function (sec) {
      var top = sec.getBoundingClientRect().top + window.scrollY;
      if (top <= probe) current = sec.id;
    });
    // 站在页面最顶端时，取第一个分区；滑到底部时，直接归到最后一个分区
    if (!current) current = visible[0].id;
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8) {
      current = visible[visible.length - 1].id;
    }
    // 滑轨里的「热榜」一个锚点替掉新收录 / 高价值榜 / 即将截止 / 抽奖四个板子：
    // 只要当前停在看板内的任一块板，就高亮这唯一的一格。
    var target = BOARD_TARGET[current] ? "hot" : current;
    navLinks.forEach(function (a) {
      var on = a.dataset.target === target;
      a.classList.toggle("active", on);
      /* 光换颜色读屏用户不知道自己在哪：当前分区同时打上 aria-current。 */
      if (on) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    });
  }

  window.addEventListener("scroll", function () {
    if (navRaf) return;
    navRaf = requestAnimationFrame(function () { navRaf = null; syncNav(); });
  }, { passive: true });
  window.addEventListener("resize", function () { syncNav(); }, { passive: true });

  navLinks.forEach(function (a) {
    a.addEventListener("click", function (ev) {
      var id = a.dataset.target;
      if (panelOf(id)) {
        ev.preventDefault();
        showTab(id);
        scrollToBoard();
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      } else if (id === "hot" && hotBoard) {
        // 合并后的「热榜」：平滑回到聚合看板顶部，看板里当前看的哪块板保持不变
        ev.preventDefault();
        var rect = hotBoard.getBoundingClientRect();
        var barH = mqMobile.matches ? 64 : 68;
        var top = window.scrollY + rect.top - barH;
        window.scrollTo({ top: Math.max(top, 0), behavior: scrollBehavior() });
        if (history.replaceState) history.replaceState(null, "", "#hot");
      }
      navLinks.forEach(function (x) { x.classList.remove("active"); x.removeAttribute("aria-current"); });
      a.classList.add("active");
      a.setAttribute("aria-current", "location");
      navJumpUntil = performance.now() + 700;
      setTimeout(syncNav, 760);
    });
  });

  /* -------------------------------------------------------------- modal */
  var modal = $("#search-modal");
  var input = $("#q");
  var lastFocus = null;

  function openModal() {
    lastFocus = document.activeElement;
    modal.classList.add("on");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    // 故意不聚焦输入框：避免手机键盘弹出遮住筛选面板
    var closeBtn = $(".sheet-close", modal);
    if (closeBtn && !mqMobile.matches) closeBtn.focus({ preventScroll: true });
  }

  function closeModal() {
    modal.classList.remove("on");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  var opener = $("#open-search");
  if (opener) opener.addEventListener("click", openModal);
  $$("[data-close]", modal).forEach(function (el) { el.addEventListener("click", closeModal); });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && modal.classList.contains("on")) closeModal();
    /* 搜索弹窗开着时把 Tab 圈在弹窗里：aria-modal="true" 只是声明，背景并没有 inert，
       不拦的话连按 Tab 会跑到页脚的「回到顶部」。首尾两个可聚焦元素之间循环。 */
    if (ev.key === "Tab" && modal.classList.contains("on")) {
      var focusables = $$(
        "a[href], button:not([disabled]), input, textarea, select, [tabindex]:not([tabindex='-1'])",
        modal
      ).filter(function (el) { return el.getClientRects().length > 0; });
      if (focusables.length) {
        var first = focusables[0];
        var last = focusables[focusables.length - 1];
        var cur = document.activeElement;
        if (!modal.contains(cur)) {
          ev.preventDefault();
          first.focus();
        } else if (ev.shiftKey && cur === first) {
          ev.preventDefault();
          last.focus();
        } else if (!ev.shiftKey && cur === last) {
          ev.preventDefault();
          first.focus();
        }
      }
    }
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
      ev.preventDefault();
      modal.classList.contains("on") ? closeModal() : openModal();
    }
    if (ev.key === "/" && !/input|textarea/i.test(document.activeElement.tagName) && !modal.classList.contains("on")) {
      ev.preventDefault();
      openModal();
    }
  });

  if (input) {
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        state.q = input.value.trim();
        render();
      }, 110);
    });
  }

  $$(".chips").forEach(function (group) {
    var key = group.dataset.group;
    group.addEventListener("click", function (ev) {
      var chip = ev.target.closest(".chip");
      if (!chip) return;
      $$(".chip", group).forEach(function (c) { c.classList.remove("on"); });
      chip.classList.add("on");
      state[key] = chip.dataset.value;
      render();
    });
  });

  function setChips(key, value) {
    var group = $('.chips[data-group="' + key + '"]');
    if (!group) return false;
    var hit = false;
    $$(".chip", group).forEach(function (c) {
      var on = c.dataset.value === value;
      c.classList.toggle("on", on);
      if (on) hit = true;
    });
    return hit;
  }

  var resetBtn = $("[data-reset]");
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      state = { q: "", time: "all", cat: "all", cost: "all", verify: "all", sort: "value" };
      if (input) input.value = "";
      $$(".chips").forEach(function (group) {
        $$(".chip", group).forEach(function (c) {
          c.classList.toggle("on", c.dataset.value === "all" || (group.dataset.group === "sort" && c.dataset.value === "value"));
        });
      });
      render();
    });
  }

  /* ------------------------------------------- URL 同步：?q=&cat=&cost=… */
  var URL_KEYS = ["cat", "cost", "verify", "time", "sort"];
  var DEFAULTS = { time: "all", cat: "all", cost: "all", verify: "all", sort: "value" };

  function syncURL() {
    if (!history.replaceState) return;
    var params = new URLSearchParams();
    if (state.q) params.set("q", state.q);
    URL_KEYS.forEach(function (k) {
      if (state[k] && state[k] !== DEFAULTS[k]) params.set(k, state[k]);
    });
    var qs = params.toString();
    var next = location.pathname + (qs ? "?" + qs : "") + location.hash;
    if (next !== location.pathname + location.search + location.hash) {
      history.replaceState(null, "", next);
    }
    /* 语言徽标的 href 跟着当前筛选 / hash 走：中键或新标签页打开也不会丢参数 */
    if (langBtn) langBtn.setAttribute("href", otherLangHref());
  }

  function restoreFromURL() {
    try {
      var params = new URLSearchParams(location.search);
      var q = params.get("q");
      if (q) {
        state.q = q;
        if (input) input.value = q;
      }
      URL_KEYS.forEach(function (k) {
        var v = params.get(k);
        if (v && v !== DEFAULTS[k] && setChips(k, v)) state[k] = v;
      });
    } catch (err) { /* 老浏览器不支持 URLSearchParams 时忽略 */ }
  }

  /* ---------------------------------------------------------- responsive */
  var onMQ = function () { render(); applyBoard(); };
  if (mqMobile.addEventListener) mqMobile.addEventListener("change", onMQ);
  else if (mqMobile.addListener) mqMobile.addListener(onMQ);

  /* ----------------------------------------------------------------- ads */
  $$(".ad-slot").forEach(function (slot) {
    if (slot.children.length > 0) slot.style.display = "block";
  });

  /* ------------------------------------------- 深链接：/ #deal-<id> 直接展开 */
  function openFromHash() {
    var m = /^#deal-(.+)$/.exec(location.hash || "");
    if (!m) return false;
    var key = m[1];
    try { key = decodeURIComponent(key); } catch (err) { /* 不是编码过的就算了 */ }
    var target = document.getElementById("deal-" + key);
    if (!target) {
      /* 首页只内联每类前 25 条：老链接 /#deal-<id> 指向没内联的条目时，
         直接落到它的独立详情页，不会变成一次「点了没反应」。 */
      location.replace(DETAIL_BASE + encodeURIComponent(key) + "/");
      return true;
    }
    document.documentElement.classList.add("deep-link");
    openCard(target);
    revealDeal(target, "auto", 80);
    requestAnimationFrame(function () {
      revealDeal(target, "auto", 80);
      setTimeout(function () { document.documentElement.classList.remove("deep-link"); }, 80);
    });
    return true;
  }

  /* 同一页里 hash 变了（点页内链接、浏览器前进 / 后退、手改地址）也要落到对应位置：
     老版本只在首次加载时看一次 hash，跳到 #deal-<id> 时卡片并不会展开、也不会滚过去。 */
  window.addEventListener("hashchange", function () {
    if (openFromHash()) return;
    var id = (location.hash || "").slice(1).replace(/^expiring$/, "closing");
    if (id && showTab(id)) {
      scrollToBoard();
      return;
    }
    syncNav();
  });

  /* ---------------------------------------------------------------- init */
  /* 语言切换：整页跳到另一语言版本（/ ↔ /en/），带上当前查询参数与 #hash。
     链接的 href 在 syncURL 里同步维护，禁用 JS 时也能直接跳到默认的对应语言首页。 */
  var langBtn = $("#lang-switch");
  if (langBtn) {
    langBtn.setAttribute("href", otherLangHref());
    langBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      location.href = otherLangHref();
    });
  }

  /* ---------------------------------- 投稿（原生 <dialog> → Apps Script 直邮）
     不加载任何第三方脚本：弹窗就是页面里的 <dialog>，表单用 fetch（no-cors）POST 到
     Apps Script Web App，由它用 MailApp 发到 vvotzs@gmail.com。接口地址写在弹窗的
     data-endpoint 上（构建时由 build_site.py 注入），换接口只改那一处。
     禁用 JS 或不支持 showModal 时，按钮本身就是 TG 群链接，不会走进死路。 */
  var submitDialog = $("#submit-dialog");
  var submitBtn = $("#open-submit");
  if (submitDialog && submitBtn && typeof submitDialog.showModal === "function") {
    var GAS_URL = submitDialog.getAttribute("data-endpoint") || "";
    var submitForm = $("#submit-form", submitDialog);
    var donePanel = $("#sd-done", submitDialog);
    var errEl = $("#sd-err", submitDialog);
    var sendBtn = $(".sd-send", submitDialog);
    var nameEl = $("#sd-f1", submitDialog);
    var urlEl = $("#sd-f2", submitDialog);
    var regionEl = $("#sd-f3", submitDialog);
    var notesEl = $("#sd-f4", submitDialog);
    var hpEl = $("#sd-hp", submitDialog);   /* 蜜罐：真人看不到也碰不到（不设 name，不用 website 免得密码管理器自动填） */
    var segEl = $("#sd-seg", submitDialog);
    var modeInputs = segEl ? $$("input[name='sd-mode']", segEl) : [];
    var modeOpts = segEl ? $$(".sd-opt", segEl) : [];
    var doneTitle = $("#sd-done-t", submitDialog);
    /* 顶部开关：「投稿」（默认）/「失效反馈」。反馈模式下名称前带【失效反馈】：
       GAS 现有主题是「[投稿] 名称 · 地区」，前缀进了名称就进了主题，gmail 搜「【失效反馈】」直接命中；
       GAS 一行不改、不重新部署。GAS 把 name 截到 80 字，所以反馈模式下名称限 74 字，给前缀留 6 个。 */
    var MODE_PREFIX = "【失效反馈】";
    var mode = "submit";
    var sending = false;
    /* 5 秒防重复冷却的起点存在 sessionStorage 里：点「再投一条」或刷新页面都还在，
       只有请求失败才清零（允许立即重试）。新开标签页 = 新会话，冷却从头算。 */
    var SENT_KEY = "ydj_last_sent";
    var COOLDOWN_MS = 5000;
    var readSentAt = function () {
      try {
        var v = parseInt(sessionStorage.getItem(SENT_KEY), 10);
        return isNaN(v) ? 0 : v;
      } catch (err) { return 0; }
    };
    var lastSentAt = readSentAt();
    var writeSentAt = function (t) {
      lastSentAt = t;
      try {
        if (t) sessionStorage.setItem(SENT_KEY, String(t));
        else sessionStorage.removeItem(SENT_KEY);
      } catch (err) { /* 隐私模式等存不了：只在内存里生效 */ }
    };
    var openedAt = 0;                        /* 弹窗打开时间：随提交带 elapsed_ms，太快的多半是脚本 */

    /* 手机端自适应：平时垂直居中；输入法把可视区域压小（或聚焦输入框）时贴到顶部。
       用 .kb-open 一个类切换，键盘收起 / 进入成功页就移除，弹窗平滑回到中间。 */
    var mqNarrow = window.matchMedia("(max-width: 680px)");
    var vp = window.visualViewport || null;
    var rootStyle = document.documentElement.style;
    var vpBaseH = 0;   /* 打开弹窗时的可视区域高度（键盘未弹起） */

    /* 把可视区域的位置和高度写成 CSS 变量，style.css 的 .kb-open 用它们算 top / max-height：
       iOS 键盘弹起时布局视口并不缩小，Safari 会把可视区域往下平移（vp.offsetTop > 0），
       只按布局视口写 top:12px 会被顶出屏幕；按可视区域算就不会。 */
    var syncViewportVars = function () {
      if (!vp) return;
      rootStyle.setProperty("--vv-top", Math.max(0, vp.offsetTop || 0).toFixed(1) + "px");
      rootStyle.setProperty("--vv-max-h", Math.max(120, vp.height || 0).toFixed(1) + "px");
    };
    var kbOpen = function (on) {
      if (!mqNarrow.matches) { submitDialog.classList.remove("kb-open"); return; }
      submitDialog.classList.toggle("kb-open", !!on);
    };
    var syncKeyboard = function () {
      if (!submitDialog.open) return;   /* 弹窗没开时不改 --vv-* / kb-open */
      if (!vp) return;
      syncViewportVars();
      /* 两种环境都成立：
         iOS —— innerHeight 不变、vp.height 变小，差值 ≈ 键盘高度；
         Android Chrome —— viewport 写了 interactive-widget=resizes-content，innerHeight 与 vp.height 一起变小，
         差值接近 0。所以再和「打开弹窗时的 vp.height」比一次，谁大听谁的。 */
      var shrunk = window.innerHeight - vp.height;
      var fromBase = vpBaseH ? vpBaseH - vp.height : 0;
      var up = shrunk > 110 || fromBase > 110;
      kbOpen(up);
      /* 键盘没弹起时基线跟着当前可视高度走：收起键盘、旋转屏幕后自己回到正确值，
         不会拿一个旧基线反复判成「键盘弹起」。 */
      if (!up) vpBaseH = vp.height;
    };
    if (vp) {
      vp.addEventListener("resize", syncKeyboard);
      vp.addEventListener("scroll", syncKeyboard);
    }
    /* 横竖屏切换 / 窗口宽度变化：可视高度整块换量级，旧基线会把「变矮」误判成键盘弹起，
       键盘没弹起时先重取基线再判断。 */
    var lastW = window.innerWidth;
    var refreshBaseH = function () {
      if (!vp || !submitDialog.open) return;
      lastW = window.innerWidth;
      /* 横竖屏 / 宽度变化和键盘无关：可视高度就是新基线（键盘若同时弹着，收起后 syncKeyboard 会再校正） */
      vpBaseH = vp.height;
      syncKeyboard();
    };
    if (window.addEventListener) {
      window.addEventListener("resize", function () {
        if (window.innerWidth !== lastW) { refreshBaseH(); return; }
        syncKeyboard();
      });
      window.addEventListener("orientationchange", function () {
        /* 方向切换后布局尺寸要等一帧才更新，稍后再取基线 */
        setTimeout(refreshBaseH, 120);
      });
    }

    var fields = [nameEl, urlEl, regionEl, notesEl];
    fields.forEach(function (el) {
      if (!el) return;
      el.addEventListener("focusin", function () {
        /* 有 visualViewport 时以「可视区域真的变小」为准（不误判）；
           老浏览器拿不到可视区域，才在聚焦时先让位 */
        if (mqNarrow.matches && !vp) kbOpen(true);
      });
      el.addEventListener("focusout", function () {
        setTimeout(function () {
          if (!fields.some(function (f) { return f && f === document.activeElement; })) kbOpen(false);
        }, 80);
      });
    });

    /* 提示文案：构建时已按页面语言写在 data-msg-<key> 上 */
    var msg = function (key) {
      return submitDialog.getAttribute("data-msg-" + key) || "";
    };

    var clearBad = function () {
      $$(".sd-row", submitDialog).forEach(function (row) { row.classList.remove("bad"); });
      errEl.textContent = "";
      errEl.hidden = true;
    };

    /* 顶部开关的实际切换：原生 radio 的选中态由 checked 决定，配一份 .on 给文字上色；
       占位文案、说明框 aria-label 与名称字数上限跟着模式走，已经填的内容一律不动。 */
    var applyPlaceholders = function (m) {
      [nameEl, urlEl, notesEl].forEach(function (el) {
        var ph = el && el.getAttribute("data-ph-" + m);
        if (ph != null) el.placeholder = ph;
      });
      if (notesEl) {
        var label = notesEl.getAttribute("data-al-" + m);
        if (label) notesEl.setAttribute("aria-label", label);
      }
      if (nameEl) nameEl.setAttribute("maxlength", m === "report" ? "74" : "80");
    };
    var setMode = function (m) {
      mode = m === "report" ? "report" : "submit";
      if (segEl) segEl.setAttribute("data-mode", mode);
      modeInputs.forEach(function (input) {
        input.checked = input.value === mode;
      });
      modeOpts.forEach(function (opt) {
        var input = $("input", opt);
        opt.classList.toggle("on", !!input && input.value === mode);
      });
      applyPlaceholders(mode);
    };
    modeInputs.forEach(function (input) {
      input.addEventListener("change", function () {
        if (!input.checked) return;
        setMode(input.value);
        clearBad();              /* 上一个模式的红字别留到新模式里 */
      });
    });
    setMode("submit");           /* 初始就是「投稿」；打开时 resetForm 还会再回一次默认 */
    var showErr = function (row, text) {
      clearBad();
      if (row) row.classList.add("bad");
      errEl.textContent = text;
      errEl.hidden = false;
    };
    /* 弹窗里没有 <form>（避开安卓 Chrome 的自动填充条），清空只能逐个写 value；
       submitForm 本身是 <div>，没有 reset()。 */
    var clearFields = function () {
      [nameEl, urlEl, regionEl, notesEl, hpEl].forEach(function (el) {
        if (el) el.value = "";
      });
    };
    var resetForm = function () {
      clearFields();
      setMode("submit");        /* 每次打开 / 「再投一条」都回到默认「投稿」 */
      /* 故意不清 lastSentAt：刷新 / 「再投一条」后 5 秒冷却继续生效，只有请求失败才清零 */
      clearBad();
      donePanel.hidden = true;
      submitForm.hidden = false;
      if (sendBtn) sendBtn.hidden = false;   /* 回到填写界面：发送按钮恢复 */
      kbOpen(false);                         /* 回到填写页 / 重新打开：回正居中 */
    };
    var showDone = function (sentMode) {
      /* 回执区分投稿与反馈：文案构建时已按页面语言写在 data-done-* 上 */
      if (doneTitle) {
        var t = submitDialog.getAttribute("data-done-" + (sentMode === "report" ? "report" : "submit"));
        if (t) doneTitle.textContent = t;
      }
      submitForm.hidden = true;     /* 同一张卡片就地换成回执，不改弹窗高度 */
      donePanel.hidden = false;
      if (sendBtn) sendBtn.hidden = true;
      kbOpen(false);                /* 成功页没有输入框：收回贴顶，回正居中 */
    };
    var openDialog = function () {
      resetForm();
      openedAt = Date.now();                 /* 提交时算 elapsed_ms */
      if (vp) {
        vpBaseH = vp.height;   /* 记下键盘未弹起时的可视高度，Android 上 innerHeight 也会缩，靠它判断 */
        syncViewportVars();
      }
      submitDialog.showModal();
      document.documentElement.classList.add("dialog-open");
      /* 桌面端直接聚焦名称框；手机端不自动聚焦，避免一打开就弹键盘、把卡片顶到最上面。
         手机端把焦点显式放在 <dialog> 自己身上（tabindex="-1"）：不这么做时浏览器会自己挑
         弹窗里第一个可聚焦元素，安卓 Chrome 就可能在打开瞬间闪出键盘上方的 🔑💳📍 填充辅助栏。 */
      if (!mqNarrow.matches) {
        setTimeout(function () { if (nameEl) nameEl.focus(); }, 40);
      } else {
        try { submitDialog.focus({ preventScroll: true }); }
        catch (err) { submitDialog.focus(); }
      }
    };
    var closeDialog = function () {
      if (submitDialog.open) submitDialog.close();
    };

    submitBtn.addEventListener("click", function (ev) {
      ev.preventDefault();            /* 按钮的 href 留给禁用 JS 时的兜底 */
      openDialog();
    });
    $$("[data-submit-close]", submitDialog).forEach(function (el) {
      el.addEventListener("click", closeDialog);
    });
    /* 点遮罩关闭：::backdrop 不是 DOM 节点，点在卡片外时事件目标是 <dialog> 本身，
       再用坐标确认一次确实落在卡片外面（填写中与提交成功页都一样生效）。
       只看坐标：落在卡片矩形内（含内边距、提交成功页的按钮区域）就不关。 */
    submitDialog.addEventListener("click", function (ev) {
      if (ev.target !== submitDialog) return;
      var r = submitDialog.getBoundingClientRect();
      var outside = ev.clientX < r.left || ev.clientX > r.right ||
                    ev.clientY < r.top || ev.clientY > r.bottom;
      if (outside) closeDialog();
    });
    submitDialog.addEventListener("close", function () {
      document.documentElement.classList.remove("dialog-open");
      kbOpen(false);
      setMode("submit");       /* 关掉后回到默认「投稿」，下次打开不会带着上次的选择 */
      rootStyle.removeProperty("--vv-top");
      rootStyle.removeProperty("--vv-max-h");
    });
    var againBtn = $("[data-submit-again]", submitDialog);
    if (againBtn) againBtn.addEventListener("click", resetForm);
    [nameEl, urlEl, regionEl].forEach(function (el) {
      if (el) el.addEventListener("input", clearBad);
    });

    /* 没有 <form>，原生 submit 不会再触发：发送按钮的点击和单行输入框的 Enter 都走这里。
       下面这一整段（蜜罐 / 5 秒冷却 / 必填校验 / 提交中态 / 回执）与原来 submit 处理器逐行一致。 */
    var doSubmit = function () {
      if (sending) return;
      /* 蜜罐字段被填 = 机器人。静默走成功回执但不发请求，让它以为提交成功。 */
      if (hpEl && hpEl.value) { showDone(mode); return; }
      /* 5 秒防重复冷却：连点 / 脚本在同一份表单里反复 POST 只会有第一次真正发出去。
         起点存在 sessionStorage，刷新或「再投一条」之后照样生效。 */
      if (Date.now() - lastSentAt < COOLDOWN_MS) {
        showErr(null, msg("wait") || (LANG === "en" ? "Please wait a few seconds." : "请等几秒再试"));
        return;
      }
      var name = (nameEl.value || "").trim();
      var url = (urlEl.value || "").trim();
      if (!name) { showErr(nameEl.parentNode, msg(mode === "report" ? "name-report" : "name")); nameEl.focus(); return; }
      /* 链接只要求非空：用户写 testdomain.com 或一段文字说明也照收，不做前缀校验 */
      if (!url) { showErr(urlEl.parentNode, msg(mode === "report" ? "link-report" : "link")); urlEl.focus(); return; }
      /* 失效反馈：名称前带【失效反馈】，GAS 发信主题就是「[投稿] 【失效反馈】活动名 · 地区」 */
      if (mode === "report") name = MODE_PREFIX + name;

      var body = new URLSearchParams();
      body.set("name", name);
      body.set("url", url);
      body.set("region", (regionEl.value || "").trim());
      body.set("notes", (notesEl.value || "").trim());
      body.set("lang", LANG);
      /* 蜜罐与停留时长一起带给 Apps Script：服务端再按 hp_x7 非空 / elapsed_ms < 1500 拦一次 */
      body.set("hp_x7", hpEl ? hpEl.value : "");
      body.set("elapsed_ms", String(openedAt ? Date.now() - openedAt : 0));

      sending = true;
      writeSentAt(Date.now());
      sendBtn.disabled = true;
      clearBad();
      var finish = function (ok) {
        sending = false;
        sendBtn.disabled = false;
        if (!ok) { writeSentAt(0); showErr(null, msg("failed")); return; }   /* 失败允许立即重试 */
        showDone(mode);
      };
      if (!GAS_URL) { finish(false); return; }
      fetch(GAS_URL, { method: "POST", mode: "no-cors", body: body })
        .then(function () { finish(true); })
        .catch(function () { finish(false); });
    };

    /* 发送：按钮点击（type="button"）；单行的三个框按 Enter 也发。
       这三个框是 <textarea rows="1">（安卓 Chrome 不会对 textarea 弹出填充辅助栏），
       所以换行得自己拦：
       - keydown 先拦一次（桌面与大多数安卓键盘）；
       - beforeinput 兜底拦 insertLineBreak / insertParagraph——Gboard 常常只给 beforeinput，
         keydown 是 keyCode 229，光靠 keydown 会漏一行换行。
       - 输入法组字中不提交；刚用回车确认完候选词（200ms 内）也不提交，
         否则拼音选词的回车会把半截内容发出去。多行说明框（sd-f4）保留正常换行，不介入。 */
    if (sendBtn) sendBtn.addEventListener("click", doSubmit);
    [nameEl, urlEl, regionEl].forEach(function (el) {
      if (!el) return;
      var composeEndedAt = 0;
      el.addEventListener("compositionend", function () { composeEndedAt = Date.now(); });
      var pickingCandidate = function () { return Date.now() - composeEndedAt < 200; };
      el.addEventListener("keydown", function (ev) {
        if (ev.key !== "Enter" || ev.isComposing || ev.keyCode === 229) return;
        ev.preventDefault();
        if (pickingCandidate()) return;   /* 这一下回车只算上屏，不发送 */
        doSubmit();
      });
      el.addEventListener("beforeinput", function (ev) {
        var type = ev.inputType;
        if (type !== "insertLineBreak" && type !== "insertParagraph") return;
        ev.preventDefault();
        if (ev.isComposing || pickingCandidate()) return;
        doSubmit();
      });
      /* 粘贴 / 拖入的多行文本折成一行：\r\n、\r、\n 都变空格，光标留在原处 */
      el.addEventListener("input", function () {
        var raw = el.value;
        if (raw.indexOf("\n") === -1 && raw.indexOf("\r") === -1) return;
        var caret = el.selectionStart == null ? raw.length : el.selectionStart;
        var head = raw.slice(0, caret).replace(/\r\n|\r|\n/g, " ");
        var tail = raw.slice(caret).replace(/\r\n|\r|\n/g, " ");
        el.value = head + tail;
        try { el.setSelectionRange(head.length, head.length); } catch (err) { /* 不支持就算了 */ }
      });
    });
  }

  /* -------------------------------------------------- 优惠内容浮层（卡片展开区） */
  /* 卡片里只留一颗胶囊，正文存在 .cf-body（display:none，SEO 照样能读到）；
     点开在浮层里显示全文：正文区自己滚动，点遮罩 / 关闭键 / Esc 收起。 */
  var cfSheet = null;
  var cfLastBtn = null;
  var cfTimer = null;
  /* 吐司开合后的 350ms 内，卡片折叠 / 空白收起一律不响应：
     同一次点击冒泡到 document 上的其它监听时，不会连锁把卡片折起来。 */
  var cfLockUntil = 0;
  function cfLocked() { return Date.now() < cfLockUntil; }
  function cfLock() { cfLockUntil = Date.now() + 350; }
  /* 优惠内容浮层停留 15 秒（普通小吐司是 2.5–3 秒）：长文有足够时间读；
     点遮罩、点浮层本身、Esc 或关闭键都能提前收起，收起时清掉定时器。 */
  var CF_MS = 15000;

  function cfClose() {
    clearTimeout(cfTimer);
    cfTimer = null;
    cfLock();
    if (!cfSheet || cfSheet.hidden) return;
    cfSheet.hidden = true;
    document.documentElement.classList.remove("cf-open");
    if (cfLastBtn) {
      cfLastBtn.setAttribute("aria-expanded", "false");
      try { cfLastBtn.focus({ preventScroll: true }); } catch (err) { cfLastBtn.focus(); }
    }
    cfLastBtn = null;
  }

  function cfEnsure() {
    if (cfSheet) return cfSheet;
    var wrap = document.createElement("div");
    wrap.className = "cf-sheet";
    wrap.hidden = true;
    wrap.innerHTML =
      '<div class="cf-card" role="dialog" aria-modal="true" aria-labelledby="cf-title">' +
        '<div class="cf-head">' +
          '<div class="cf-hmain"><span class="cf-eyebrow"></span>' +
            '<h2 class="cf-title" id="cf-title"></h2><span class="cf-badge" hidden></span></div>' +
          '<button class="cf-close" type="button" aria-label="' + '关闭' + '">\u00d7</button>' +
        '</div>' +
        '<div class="cf-text"></div>' +
        '<div class="cf-foot"><span class="cf-foot-dot" aria-hidden="true"></span><span class="cf-foot-t"></span></div>' +
      '</div>';
    document.body.appendChild(wrap);
    wrap.addEventListener("click", function (ev) {
      var text = ev.target.closest ? ev.target.closest(".cf-text") : null;
      /* 正文还能滚（长文）时点正文不算关闭，免得起手就收起；短到不用滚就随手关掉 */
      if (text && text.scrollHeight > text.clientHeight + 2) return;
      cfClose();
    });
    wrap.querySelector(".cf-close").addEventListener("click", cfClose);
    cfSheet = wrap;
    return wrap;
  }

  function cfOpen(btn) {
    var field = btn.closest(".cf-field");
    var body = field && field.querySelector(".cf-body");
    if (!body) return;
    var sheet = cfEnsure();
    var field2 = btn.closest(".cf-field") || field;
    var kind = btn.querySelector(".cf-kind");
    sheet.querySelector(".cf-eyebrow").textContent = kind ? kind.textContent : "";
    sheet.querySelector(".cf-title").textContent = field2.getAttribute("data-cf-title") || "";
    var badge = sheet.querySelector(".cf-badge");
    var bv = field2.getAttribute("data-cf-value") || "";
    badge.textContent = bv;
    badge.hidden = !bv;
    sheet.querySelector(".cf-foot-t").textContent = field2.getAttribute("data-cf-foot") || "";
    var text = sheet.querySelector(".cf-text");
    text.textContent = (body.textContent || "").trim();
    text.scrollTop = 0;
    sheet.hidden = false;
    document.documentElement.classList.add("cf-open");
    btn.setAttribute("aria-expanded", "true");
    cfLastBtn = btn;
    clearTimeout(cfTimer);
    cfLock();
    cfTimer = setTimeout(cfClose, CF_MS);
    try { sheet.querySelector(".cf-close").focus({ preventScroll: true }); } catch (err) { /* 老浏览器 */ }
  }

  /* 捕获阶段先拦下：既不触发展开卡折叠，也不让点击冒到卡片头部 */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest ? ev.target.closest(".cf-btn") : null;
    if (!btn) return;
    ev.preventDefault();
    /* 同一个节点（document）上还挂着卡片折叠的监听：必须 stopImmediatePropagation，
       只 stopPropagation 拦不住同节点的其它监听，展开卡会在点开吐司的瞬间被折起来。 */
    ev.stopImmediatePropagation();
    cfOpen(btn);
  }, true);

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") cfClose();
  });

  restoreFromURL();
  if (langBtn) langBtn.setAttribute("href", otherLangHref());
  render();   /* 首次渲染：分页、计数、语言徽标链接（页面已是单语，无需再切文案） */
  var hash = (location.hash || "").slice(1);
  if (hash === "expiring") hash = "closing";
  if (!showTab(hash)) applyBoard();
  openFromHash();
  syncNav();
})();
