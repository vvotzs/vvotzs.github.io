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
  /* 每页只带自己语言的索引（扁平 {id: 文本}）；旧的双语嵌套格式也能读。 */
  var SEARCH = {};
  var indexEl = $("#search-index");
  if (indexEl) {
    try {
      var rawIndex = JSON.parse(indexEl.textContent) || {};
      var flat = rawIndex.zh || rawIndex.en ? (rawIndex[LANG] || rawIndex.zh || {}) : rawIndex;
      Object.keys(flat).forEach(function (id) { SEARCH[id] = String(flat[id]).toLowerCase(); });
    } catch (err) { SEARCH = {}; }
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

  /* --------------------------------------------------------------- state */
  var state = { q: "", time: "all", cat: "all", cost: "all", verify: "all", sort: "value" };

  var TODAY = new Date();
  TODAY.setHours(0, 0, 0, 0);
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

    var added = cardDate(card, "added");
    var end = cardDate(card, "end");

    if (state.time === "24h") {
      if (!added || TODAY - added > DAY) return false;
    } else if (state.time === "48h") {
      if (!added || TODAY - added > DAY * TODAY_WINDOW_DAYS) return false;
    } else if (state.time === "7d") {
      if (!added || TODAY - added > DAY * 7) return false;
    } else if (state.time === "past") {
      var isOld = added && TODAY - added > DAY * 7;
      var isOver = end && end < TODAY;
      if (!isOld && !isOver) return false;
    }
    return true;
  }

  function sortCards(list, anchor) {
    if (anchor === "rank" || anchor === "archive" || anchor === "lottery") return;
    var by = state.sort;
    list.sort(function (a, b) {
      if (by === "new") {
        return (b.dataset.added || "").localeCompare(a.dataset.added || "") ||
               (+b.dataset.valExp || 0) - (+a.dataset.valExp || 0);
      }
      if (by === "end") {
        var ea = a.dataset.end || "9999-12-31";
        var eb = b.dataset.end || "9999-12-31";
        return ea.localeCompare(eb);
      }
      return (+b.dataset.valExp || 0) - (+a.dataset.valExp || 0);
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
    track.textContent = "";
    if (paged) {
      var per = perOf(m);
      for (var i = 0; i < visible.length; i += per) {
        var page = document.createElement("div");
        page.className = "page";
        visible.slice(i, i + per).forEach(function (el) {
          el.classList.remove("is-extra");
          page.appendChild(el);
        });
        track.appendChild(page);
      }
    } else {
      visible.forEach(function (el) {
        el.classList.remove("is-extra");
        track.appendChild(el);
      });
    }
    track.scrollLeft = 0;
  }

  function pageCount(m) {
    return Math.max(1, Math.ceil(m.total / perOf(m)));
  }

  /* 页码 1 / N 与左右按钮的可用状态，跟着横滑位置走 */
  function updateBar(m) {
    if (!m.bar) return;
    var pages = pageCount(m);
    var show = !m.isJump && m.total > 0 && pages > 1;
    m.bar.style.display = show ? "flex" : "none";
    if (!show) return;
    var w = m.track.clientWidth || 1;
    var idx = Math.min(Math.max(Math.round(m.track.scrollLeft / w), 0), pages - 1);
    if (m.label) m.label.textContent = (idx + 1) + " / " + pages;
    var prev = $("[data-prev]", m.bar);
    var next = $("[data-next]", m.bar);
    if (prev) prev.disabled = idx <= 0;
    if (next) next.disabled = idx >= pages - 1;
  }

  function render() {
    var seen = {};
    var matchedTotal = 0;

    modules.forEach(function (m) {
      var visible = m.items.filter(matches);
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
      $$('[data-tabcount="' + m.anchor + '"]').forEach(function (el) {
        el.textContent = visible.length;
      });
      if (m.empty) m.empty.style.display = visible.length ? "none" : "block";

      var paged = !m.isJump;
      buildTrack(m, visible, paged);
      if (m.track) m.track.style.display = visible.length ? "" : "none";

      // 桌面端也不再折叠：分类内一律翻页
      m.el.dataset.collapsed = "0";
      if (m.more) m.more.hidden = true;

      updateBar(m);
    });

    $$("[data-result]").forEach(function (el) { el.textContent = matchedTotal; });
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
    window.scrollTo({ top: Math.max(top, 0), behavior: "smooth" });
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
    if (ev.target.closest(".go") || ev.target.closest(".url-link")) return; // 直达链接不触发折叠
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
    revealDeal(target, "smooth", 90);
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
    closeAll(null);
  });

  /* ------------------------------------------------------------ 滑轨高亮 */
  var navLinks = $$(".rail a[data-target]");
  var sections = $$(".module");
  var navRaf = null;

  function syncNav() {
    if (!navLinks.length) return;
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
    navLinks.forEach(function (a) {
      a.classList.toggle("active", a.dataset.target === current);
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
      }
      navLinks.forEach(function (x) { x.classList.remove("active"); });
      a.classList.add("active");
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
    if (!m) return;
    var target = document.getElementById("deal-" + m[1]);
    if (!target) return;
    document.documentElement.classList.add("deep-link");
    openCard(target);
    revealDeal(target, "auto", 80);
    requestAnimationFrame(function () {
      revealDeal(target, "auto", 80);
      setTimeout(function () { document.documentElement.classList.remove("deep-link"); }, 80);
    });
  }

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
    var nameEl = $("#sd-name", submitDialog);
    var urlEl = $("#sd-url", submitDialog);
    var regionEl = $("#sd-region", submitDialog);
    var notesEl = $("#sd-notes", submitDialog);
    var sending = false;

    /* 手机端自适应：平时垂直居中；输入法把可视区域压小（或聚焦输入框）时贴到顶部。
       用 .kb-open 一个类切换，键盘收起 / 进入成功页就移除，弹窗平滑回到中间。 */
    var mqNarrow = window.matchMedia("(max-width: 680px)");
    var vp = window.visualViewport || null;
    var kbOpen = function (on) {
      if (!mqNarrow.matches) { submitDialog.classList.remove("kb-open"); return; }
      submitDialog.classList.toggle("kb-open", !!on);
    };
    var syncKeyboard = function () {
      if (!vp) return;
      var shrunk = window.innerHeight - vp.height;   /* 键盘占掉的高度 */
      kbOpen(shrunk > 110);
    };
    if (vp) {
      vp.addEventListener("resize", syncKeyboard);
      vp.addEventListener("scroll", syncKeyboard);
    }
    if (window.addEventListener) {
      window.addEventListener("resize", syncKeyboard);
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
    var showErr = function (row, text) {
      clearBad();
      if (row) row.classList.add("bad");
      errEl.textContent = text;
      errEl.hidden = false;
    };
    var resetForm = function () {
      submitForm.reset();
      clearBad();
      donePanel.hidden = true;
      submitForm.hidden = false;
      if (sendBtn) sendBtn.hidden = false;   /* 回到填写界面：发送按钮恢复 */
      kbOpen(false);                         /* 回到填写页 / 重新打开：回正居中 */
    };
    var openDialog = function () {
      resetForm();
      submitDialog.showModal();
      document.documentElement.classList.add("dialog-open");
      /* 桌面端直接聚焦名称框；手机端不自动聚焦，避免一打开就弹键盘、把卡片顶到最上面 */
      if (!mqNarrow.matches) {
        setTimeout(function () { if (nameEl) nameEl.focus(); }, 40);
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
    });
    var againBtn = $("[data-submit-again]", submitDialog);
    if (againBtn) againBtn.addEventListener("click", resetForm);
    [nameEl, urlEl, regionEl].forEach(function (el) {
      if (el) el.addEventListener("input", clearBad);
    });

    submitForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (sending) return;
      var name = (nameEl.value || "").trim();
      var url = (urlEl.value || "").trim();
      if (!name) { showErr(nameEl.parentNode, msg("name")); nameEl.focus(); return; }
      /* 链接只要求非空：用户写 testdomain.com 或一段文字说明也照收，不做前缀校验 */
      if (!url) { showErr(urlEl.parentNode, msg("link")); urlEl.focus(); return; }

      var body = new URLSearchParams();
      body.set("name", name);
      body.set("url", url);
      body.set("region", (regionEl.value || "").trim());
      body.set("notes", (notesEl.value || "").trim());
      body.set("lang", LANG);

      sending = true;
      sendBtn.disabled = true;
      clearBad();
      var finish = function (ok) {
        sending = false;
        sendBtn.disabled = false;
        if (!ok) { showErr(null, msg("failed")); return; }
        submitForm.hidden = true;     /* 同一张卡片就地换成回执，不改弹窗高度 */
        donePanel.hidden = false;
        if (sendBtn) sendBtn.hidden = true;
        kbOpen(false);                /* 成功页没有输入框：收回贴顶，回正居中 */
      };
      if (!GAS_URL) { finish(false); return; }
      fetch(GAS_URL, { method: "POST", mode: "no-cors", body: body })
        .then(function () { finish(true); })
        .catch(function () { finish(false); });
    });
  }

  restoreFromURL();
  if (langBtn) langBtn.setAttribute("href", otherLangHref());
  render();   /* 首次渲染：分页、计数、语言徽标链接（页面已是单语，无需再切文案） */
  var hash = (location.hash || "").slice(1);
  if (hash === "expiring") hash = "closing";
  if (!showTab(hash)) applyBoard();
  openFromHash();
  syncNav();
})();
