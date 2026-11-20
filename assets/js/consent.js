/* 羊毛情报局 — Cookie 同意（Consent）管理
   全站共用的一份轻量脚本：首页 / 分类页 / 详情页 / 合规页都加载它。
   1. 把选择存进 localStorage["dh_consent_v1"]（necessary / analytics / ads / ts）；
   2. 暴露 window.__dhConsent（get / has / allows / set / open）与 dh:consent-changed 事件，
      以后接 GA4 / AdSense 时按同意状态按需加载，不在页面里散落判断；
   3. 面板用 position: fixed 的底部抽屉，打开前后都不推动页面（零 CLS）；
   4. 默认由页脚「Cookie 设置」打开；只有 <html data-consent-required="1"> 且访客还没做过
      选择、又处在需要同意的地区时，才在首访自动弹出；当前站点零追踪脚本，构建时给的
      是 "0"，不会主动打扰任何人。
   文案在脚本里中英成对维护，构建时页面只带 data-lang，不额外增加 HTML 体积。 */
(function () {
  "use strict";

  var KEY = "dh_consent_v1";
  var root = document.documentElement;
  var LANG = root.getAttribute("data-lang") === "en" ? "en" : "zh";
  var REQUIRED = root.getAttribute("data-consent-required") === "1";
  var PRIVACY_HREF = (LANG === "en" ? "/en" : "") + "/privacy/";

  var T = {
    zh: {
      title: "Cookie 设置",
      lead: "本站目前只用必要的本地存储，不加载统计或广告脚本。你可以选择允许哪些类别，之后随时在页脚改回来。",
      necessary: "必要",
      necessaryDesc: "投稿冷却与这份同意记录，关掉站点就无法正常工作。",
      always: "始终开启",
      analytics: "统计",
      analyticsDesc: "匿名访问量与页面偏好，例如日后接入 Google Analytics。",
      ads: "广告",
      adsDesc: "个性化广告，例如日后接入 Google AdSense。",
      essential: "仅必要",
      save: "保存选择",
      all: "全部接受",
      close: "关闭",
      policy: "隐私政策"
    },
    en: {
      title: "Cookie Settings",
      lead: "This site uses only necessary local storage today, with no analytics or ad scripts. Choose what you allow; you can change it in the footer any time.",
      necessary: "Necessary",
      necessaryDesc: "Submit cooldown and this consent record. The site cannot work without them.",
      always: "Always on",
      analytics: "Analytics",
      analyticsDesc: "Anonymous traffic and page preferences, e.g. Google Analytics if added later.",
      ads: "Ads",
      adsDesc: "Personalised advertising, e.g. Google AdSense if added later.",
      essential: "Essential only",
      save: "Save choices",
      all: "Accept all",
      close: "Close",
      policy: "Privacy policy"
    }
  };
  var t = T[LANG];

  /* ------------------------------------------------------------ 读写同意状态 */
  /* 只接受布尔值：localStorage 里的值可能被手动改过，脏数据一律当作「没选过」。 */
  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return null;
      var v = JSON.parse(raw);
      if (!v || typeof v !== "object") return null;
      return {
        necessary: true,
        analytics: v.analytics === true,
        ads: v.ads === true,
        ts: typeof v.ts === "string" ? v.ts : ""
      };
    } catch (err) { return null; }
  }

  var state = read();

  function snapshot() {
    return state
      ? { necessary: true, analytics: state.analytics, ads: state.ads, ts: state.ts }
      : null;
  }

  function emit() {
    var detail = snapshot();
    try {
      document.dispatchEvent(new CustomEvent("dh:consent-changed", { detail: detail }));
    } catch (err) { /* 极老的浏览器没有 CustomEvent：不影响存储与后续读取 */ }
  }

  function persist(next) {
    state = {
      necessary: true,
      analytics: !!(next && next.analytics),
      ads: !!(next && next.ads),
      ts: new Date().toISOString()
    };
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (err) { /* 隐私模式存不了：本次会话仍按内存里的选择生效 */ }
    emit();
    /* 以后接入统计 / 广告就在这里按 state 加载，例如：
       if (state.analytics) loadAnalytics();
       if (state.ads) loadAds(); */
    return snapshot();
  }

  window.__dhConsent = {
    get: snapshot,
    has: function () { return !!state; },
    allows: function (kind) { return !!(state && state[kind] === true); },
    set: function (next) { return persist(next); },
    open: function () { openPanel(); }
  };

  /* ------------------------------------------------------------ 面板 */
  var panel = null;
  var lastFocus = null;
  var checkAnalytics = null;
  var checkAds = null;

  function build() {
    panel = document.createElement("div");
    panel.className = "consent";
    panel.id = "dh-consent";
    panel.setAttribute("aria-hidden", "true");
    panel.innerHTML =
      '<div class="consent-scrim" data-consent-close></div>' +
      '<section class="consent-card" role="dialog" aria-modal="true" aria-labelledby="dh-consent-title">' +
        '<div class="consent-head">' +
          '<h2 class="consent-title" id="dh-consent-title">' + t.title + '</h2>' +
          '<button class="consent-x" type="button" data-consent-close aria-label="' + t.close + '">' +
            '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5.2 5.2 14.8 14.8M14.8 5.2 5.2 14.8"/></svg>' +
          '</button>' +
        '</div>' +
        '<p class="consent-lead">' + t.lead + '</p>' +
        '<ul class="consent-list">' +
          '<li class="consent-row is-fixed">' +
            '<div class="consent-copy"><b>' + t.necessary + '</b><small>' + t.necessaryDesc + '</small></div>' +
            '<span class="consent-always">' + t.always + '</span>' +
          '</li>' +
          '<li class="consent-row">' +
            '<div class="consent-copy"><b>' + t.analytics + '</b><small>' + t.analyticsDesc + '</small></div>' +
            '<label class="consent-sw"><input type="checkbox" data-consent-cat="analytics" aria-label="' + t.analytics + '">' +
              '<span class="consent-track" aria-hidden="true"><i></i></span></label>' +
          '</li>' +
          '<li class="consent-row">' +
            '<div class="consent-copy"><b>' + t.ads + '</b><small>' + t.adsDesc + '</small></div>' +
            '<label class="consent-sw"><input type="checkbox" data-consent-cat="ads" aria-label="' + t.ads + '">' +
              '<span class="consent-track" aria-hidden="true"><i></i></span></label>' +
          '</li>' +
        '</ul>' +
        '<div class="consent-actions">' +
          '<button class="consent-btn" type="button" data-consent-essential>' + t.essential + '</button>' +
          '<button class="consent-btn" type="button" data-consent-save>' + t.save + '</button>' +
          '<button class="consent-btn mint" type="button" data-consent-all>' + t.all + '</button>' +
        '</div>' +
        '<p class="consent-foot"><a href="' + PRIVACY_HREF + '">' + t.policy + '</a></p>' +
      '</section>';
    document.body.appendChild(panel);

    checkAnalytics = panel.querySelector('[data-consent-cat="analytics"]');
    checkAds = panel.querySelector('[data-consent-cat="ads"]');

    panel.addEventListener("click", function (ev) {
      var el = ev.target;
      if (el && el.closest && el.closest("[data-consent-close]")) { closePanel(); return; }
      if (el && el.closest && el.closest("[data-consent-essential]")) {
        persist({ analytics: false, ads: false });
        closePanel();
        return;
      }
      if (el && el.closest && el.closest("[data-consent-save]")) {
        persist({ analytics: !!(checkAnalytics && checkAnalytics.checked),
                  ads: !!(checkAds && checkAds.checked) });
        closePanel();
        return;
      }
      if (el && el.closest && el.closest("[data-consent-all]")) {
        persist({ analytics: true, ads: true });
        closePanel();
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (!panel || !panel.classList.contains("is-open")) return;
      if (ev.key === "Escape" || ev.keyCode === 27) { ev.preventDefault(); closePanel(); return; }
      /* Tab 只在面板内循环：aria-modal 的对话框不能让焦点跑到背后的页面上 */
      if (ev.key === "Tab" || ev.keyCode === 9) {
        var items = panel.querySelectorAll("button, a[href], input:not([type=hidden])");
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
    });
  }

  function syncChecks() {
    if (checkAnalytics) checkAnalytics.checked = !!(state && state.analytics);
    if (checkAds) checkAds.checked = !!(state && state.ads);
  }

  function openPanel() {
    if (!panel) build();
    if (!panel) return;
    syncChecks();
    lastFocus = document.activeElement;
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    var first = panel.querySelector("[data-consent-essential]");
    if (first) { try { first.focus({ preventScroll: true }); } catch (err) { first.focus(); } }
  }

  function closePanel() {
    if (!panel) return;
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    if (lastFocus && lastFocus.focus) {
      try { lastFocus.focus({ preventScroll: true }); } catch (err) {}
    }
  }

  /* 页脚「Cookie 设置」：事件委托，任何页面（首页 / 分类 / 详情 / 合规页）都生效。 */
  document.addEventListener("click", function (ev) {
    var el = ev.target;
    if (el && el.closest && el.closest("[data-consent-open]")) {
      ev.preventDefault();
      openPanel();
    }
  });

  /* ------------------------------------------------------------ 首访自动弹出 */
  /* 只有构建时把 CONSENT_REQUIRED 改成 "1"（真的接了统计 / 广告）才会走到这里；
     已做过选择的访客永不重复弹。按浏览器时区粗略判断 EU/EEA/UK/CH，其他地方先不打扰。 */
  function inConsentRegion() {
    try {
      var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      return /^Europe\//.test(tz) || /^Atlantic\/(Canary|Madeira|Reykjavik|Faroe)$/.test(tz);
    } catch (err) { return false; }
  }

  if (REQUIRED && !state && inConsentRegion()) {
    var start = function () { openPanel(); };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }
})();
