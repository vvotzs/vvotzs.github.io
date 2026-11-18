/* 羊毛情报局 — interaction layer
   1. 单开手风琴    2. 搜索 / 筛选（改 DOM，不重新请求数据）
   3. 移动端横向分页 4. 竖版滑轨高亮          5. 图标兜底
   6. 今日 / 榜单 / 截止的跳转卡落到分类详情
   7. 筛选状态同步到 URL（?q=&cat=…），刷新 / 分享后还原
   静态卡片已在 HTML 里，脚本只做增强，禁用 JS 也能正常阅读。 */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var PAGE_SIZE = 4;            // 分类卡一页 4 条
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

  /* ------------------------------------------------------------- modules */
  var modules = $$(".module").map(function (sec) {
    var isJump = sec.dataset.kind === "jump";
    return {
      el: sec,
      anchor: sec.id,
      isJump: isJump,
      per: parseInt(sec.dataset.per, 10) || PAGE_SIZE,
      track: $("[data-track]", sec),
      bar: $("[data-bar]", sec),
      label: $("[data-label]", sec),
      countEl: $("[data-count]", sec),
      empty: $(".module-empty", sec),
      items: $$(isJump ? ".jump" : ".card", sec),
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
      var hay = ((card.dataset.hay || "") + " " + (card.dataset.cat || "")).toLowerCase();
      var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var i = 0; i < terms.length; i++) {
        if (hay.indexOf(terms[i]) === -1) return false;
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
    if (anchor === "rank" || anchor === "archive") return;
    var by = state.sort;
    list.sort(function (a, b) {
      if (by === "new") {
        return (b.dataset.added || "").localeCompare(a.dataset.added || "") ||
               (+b.dataset.val || 0) - (+a.dataset.val || 0);
      }
      if (by === "end") {
        var ea = a.dataset.end || "9999-12-31";
        var eb = b.dataset.end || "9999-12-31";
        return ea.localeCompare(eb);
      }
      return (+b.dataset.valExp || +b.dataset.val || 0) - (+a.dataset.valExp || +a.dataset.val || 0);
    });
  }

  /* ------------------------------------------------------------ rendering */
  function buildDesktop(m, list) {
    var grid = document.createElement("div");
    grid.className = "grid";
    list.forEach(function (c) { grid.appendChild(c); });
    m.track.textContent = "";
    m.track.appendChild(grid);
  }

  function buildMobile(m, list) {
    m.track.textContent = "";
    if (!list.length) return;
    for (var i = 0; i < list.length; i += m.per) {
      var page = document.createElement("div");
      page.className = "page";
      list.slice(i, i + m.per).forEach(function (c) { page.appendChild(c); });
      m.track.appendChild(page);
    }
    m.track.scrollLeft = 0;
  }

  function updateBar(m) {
    if (!m.bar) return;
    var per = m.per;
    var scroll = m.track.scrollLeft;
    var w = m.track.clientWidth || 1;
    var idx = Math.min(Math.max(Math.round(scroll / w), 0), Math.max(Math.ceil(m.total / per) - 1, 0));
    var start = m.total ? idx * per + 1 : 0;
    var end = Math.min(m.total, (idx + 1) * per);
    if (m.label) m.label.textContent = start + "–" + end + " / " + m.total;
    var prev = $("[data-prev]", m.bar);
    var next = $("[data-next]", m.bar);
    if (prev) prev.disabled = idx <= 0;
    if (next) next.disabled = (idx + 1) * per >= m.total;
  }

  function render() {
    var mobile = mqMobile.matches;
    var seen = {};
    var matchedTotal = 0;

    modules.forEach(function (m) {
      var visible = m.items.filter(matches);
      if (!m.isJump) sortCards(visible, m.anchor);
      m.total = visible.length;

      // 只数分类区里的完整卡：每个 data-key 只算一次，
      // 今日 / 榜单 / 截止里的跳转卡不参与计数，避免「匹配 N 条」翻倍。
      if (!m.isJump) {
        visible.forEach(function (el) {
          var key = el.dataset.key;
          if (key && seen[key]) return;
          if (key) seen[key] = 1;
          matchedTotal++;
        });
      }

      if (m.countEl) m.countEl.textContent = visible.length;
      if (m.empty) m.empty.style.display = visible.length ? "none" : "block";
      m.track.style.display = visible.length ? "" : "none";
      if (m.bar) m.bar.style.display = visible.length && mobile ? "flex" : "none";

      if (mobile) buildMobile(m, visible);
      else buildDesktop(m, visible);

      if (mobile) updateBar(m);
    });

    $$("[data-result]").forEach(function (el) { el.textContent = matchedTotal; });
    syncURL();
  }

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
  }

  /* 点卡片头部（链接以外的地方）或「详情」按钮都能开合 */
  document.addEventListener("click", function (ev) {
    var card = ev.target.closest(".card");
    if (!card) return;
    if (ev.target.closest(".go") || ev.target.closest(".url-link")) return; // 直达链接不触发折叠
    var head = ev.target.closest(".card-head");
    var toggle = ev.target.closest(".toggle");
    if (!head && !toggle) return;

    ev.preventDefault();
    if (card.classList.contains("open")) setOpen(card, false);
    else openCard(card);
  });

  /* 跳转卡：滚到分类区对应的唯一详情卡并展开 */
  document.addEventListener("click", function (ev) {
    var jump = ev.target.closest("[data-jump]");
    if (!jump) return;
    var key = jump.dataset.jump;
    var target = document.getElementById(key);
    if (!target) return;
    ev.preventDefault();
    openCard(target);
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
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

  /* -------------------------------------------------------------- pager */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-prev], [data-next]");
    if (!btn) return;
    var m = modules.filter(function (x) { return x.bar && x.bar.contains(btn); })[0];
    if (!m) return;
    var dir = btn.hasAttribute("data-prev") ? -1 : 1;
    m.track.scrollBy({ left: dir * m.track.clientWidth, behavior: "smooth" });
  });

  var scrollTick = {};
  document.addEventListener("scroll", function (ev) {
    var track = ev.target;
    if (!track || !track.hasAttribute || !track.hasAttribute("data-track")) return;
    var m = modules.filter(function (x) { return x.track === track; })[0];
    if (!m || !mqMobile.matches) return;
    clearTimeout(scrollTick[m.anchor]);
    scrollTick[m.anchor] = setTimeout(function () { updateBar(m); }, 90);
  }, true);

  /* --------------------------------------------------------------- rail */
  var railLinks = $$(".rail a");
  var sections = $$(".module");
  var railRaf = null;

  function syncRail() {
    var y = window.scrollY + 120;
    var current = sections[0];
    sections.forEach(function (sec) {
      if (sec.offsetTop <= y) current = sec;
    });
    if (!current) return;
    railLinks.forEach(function (a) {
      a.classList.toggle("active", a.dataset.target === current.id);
    });
  }

  window.addEventListener("scroll", function () {
    if (railRaf) return;
    railRaf = requestAnimationFrame(function () { railRaf = null; syncRail(); });
  }, { passive: true });

  railLinks.forEach(function (a) {
    a.addEventListener("click", function () {
      railLinks.forEach(function (x) { x.classList.remove("active"); });
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
  var onMQ = function () { render(); };
  if (mqMobile.addEventListener) mqMobile.addEventListener("change", onMQ);
  else if (mqMobile.addListener) mqMobile.addListener(onMQ);

  /* ----------------------------------------------------------------- ads */
  $$(".ad-slot").forEach(function (slot) {
    if (slot.children.length > 0) slot.style.display = "block";
  });

  /* ---------------------------------------------------------------- init */
  restoreFromURL();
  render();
  syncRail();
})();
