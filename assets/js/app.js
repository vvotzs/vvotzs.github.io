/* 羊毛情报局 — interaction layer
   1. 单开手风琴（手机端整卡可点）          2. 搜索 / 筛选 / 排序（读 JSON 索引）
   3. 分类内「显示更多」折叠（不再横滑翻页） 4. 热榜板 tab（桌面双板 / 手机单板）
   5. 顶部横滑分类条 + 右侧竖版滑轨高亮      6. 图标兜底
   7. 跳转卡落到分类详情                    8. 筛选状态同步到 URL
   静态卡片已在 HTML 里，脚本只做增强，禁用 JS 也能正常阅读。 */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var MORE_LIMIT = 8;           // 分类内先展示 8 条，其余折叠
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

  /* ------------------------------------------------------- 搜索索引（JSON） */
  var SEARCH = {};
  var indexEl = $("#search-index");
  if (indexEl) {
    try {
      SEARCH = JSON.parse(indexEl.textContent) || {};
      Object.keys(SEARCH).forEach(function (k) {
        SEARCH[k] = String(SEARCH[k]).toLowerCase();
      });
    } catch (err) { SEARCH = {}; }
  }

  /* ------------------------------------------------------------- modules */
  var modules = $$(".module").map(function (sec) {
    return {
      el: sec,
      anchor: sec.id,
      isJump: sec.dataset.kind === "jump",
      grid: $("[data-grid]", sec),
      countEl: $("[data-count]", sec),
      empty: $(".module-empty", sec),
      more: $("[data-more]", sec),
      items: $$(sec.dataset.kind === "jump" ? ".jump" : ".card", sec),
      expanded: false,
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

      var limit = m.isJump ? visible.length : MORE_LIMIT;
      if (m.grid) {
        m.grid.textContent = "";
        visible.forEach(function (el, i) {
          if (i >= limit) el.classList.add("is-extra");
          else el.classList.remove("is-extra");
          m.grid.appendChild(el);
        });
        m.grid.style.display = visible.length ? "" : "none";
      }

      var collapsed = !m.isJump && visible.length > MORE_LIMIT && !m.expanded;
      m.el.dataset.collapsed = collapsed ? "1" : "0";

      if (m.more) {
        if (!m.isJump && visible.length > MORE_LIMIT) {
          m.more.hidden = false;
          m.more.textContent = m.expanded
            ? "收起（只看前 " + MORE_LIMIT + " 条）"
            : "显示更多（剩余 " + (visible.length - MORE_LIMIT) + " 条）";
        } else {
          m.more.hidden = true;
        }
      }
    });

    $$("[data-result]").forEach(function (el) { el.textContent = matchedTotal; });
    syncNav();
    syncURL();
  }

  /* 各分类的「显示更多 / 收起」 */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-more]");
    if (!btn) return;
    var m = modules.filter(function (x) { return x.el.contains(btn); })[0];
    if (!m) return;
    m.expanded = !m.expanded;
    render();
  });

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
    var barH = mqMobile.matches ? 104 : 56;
    if (rect.top >= barH && rect.top <= window.innerHeight - 140) return;
    var top = window.scrollY + rect.top - barH;
    window.scrollTo({ top: Math.max(top, 0), behavior: "smooth" });
  }

  /* 顶部 tab、手机分类条、右侧滑轨里指向热榜的入口都落到同一块板 */
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
      toggle.setAttribute("aria-label", open ? "收起详情" : "展开详情");
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

  function revealDeal(target, behavior, offset) {
    var rect = target.getBoundingClientRect();
    var top = window.scrollY + rect.top - (offset == null ? 80 : offset);
    window.scrollTo({ top: Math.max(top, 0), behavior: behavior || "auto" });
  }

  /* 跳转卡：滚到分类区对应的唯一详情卡并展开（被「显示更多」收起来的先展开） */
  document.addEventListener("click", function (ev) {
    var jump = ev.target.closest("[data-jump]");
    if (!jump) return;
    var key = jump.dataset.jump;
    var target = document.getElementById(key);
    if (!target) return;
    ev.preventDefault();

    var host = modules.filter(function (m) { return m.el.contains(target); })[0];
    if (host && host.el.dataset.collapsed === "1") {
      host.expanded = true;
      render();
    }
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

  /* ------------------------------------------------------ rail / catbar 高亮 */
  var navLinks = $$(".rail a[data-target], .catbar a[data-target]");
  var sections = $$(".module");
  var navRaf = null;

  function syncNav() {
    if (!navLinks.length) return;
    var probe = window.scrollY + (mqMobile.matches ? 150 : 120);
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
    var host = modules.filter(function (mod) { return mod.el.contains(target); })[0];
    if (host && host.el.dataset.collapsed === "1") {
      host.expanded = true;
      render();
    }
    openCard(target);
    revealDeal(target, "auto", 80);
    requestAnimationFrame(function () {
      revealDeal(target, "auto", 80);
      setTimeout(function () { document.documentElement.classList.remove("deep-link"); }, 80);
    });
  }

  /* ---------------------------------------------------------------- init */
  restoreFromURL();
  render();
  var hash = (location.hash || "").slice(1);
  if (hash === "expiring") hash = "closing";
  if (!showTab(hash)) applyBoard();
  openFromHash();
  syncNav();
})();
