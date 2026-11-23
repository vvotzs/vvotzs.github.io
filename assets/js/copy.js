/* 「官方活动链接」那一行的网址：点按复制，不再跳转（2026-11-23 Jun 要求）。
   跳转仍由卡片右上 / 底部的官网 ↗、原文 ↗ 按钮承担，这里只管把地址抄进剪贴板。

   为什么单独一个文件：首页加载 app.js，440 多个详情页只加载 consent.js / votes.js，
   复制在这两类页面上都要能用，所以抽成一个两边都引的小脚本（~1KB，缓存在全站共用）。

   吐司文案不在 JS 里写死：构建时按页面语言写进 <meta name="dh-copy">，
   中文「已复制链接」、英文「Link copied」由 scripts/i18n.py 一处维护。 */
(function () {
  var meta = document.querySelector('meta[name="dh-copy"]');
  var bits = ((meta && meta.getAttribute("content")) || "").split("|");
  var DONE = bits[0] || "已复制链接";
  var MANUAL = bits[1] || DONE;

  var toast = null;
  var toastTimer = null;

  function ensureToast() {
    if (toast) return toast;
    toast = document.createElement("div");
    toast.className = "copy-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.hidden = true;
    document.body.appendChild(toast);
    return toast;
  }

  /* 吐司贴在按钮下方，左右夹进视口；下面放不下就翻到上方（键盘弹起 / 屏幕很矮时） */
  function place(btn) {
    var pad = 8;
    var r = btn.getBoundingClientRect();
    var w = toast.offsetWidth;
    var h = toast.offsetHeight;
    var left = r.left + Math.min(30, r.width / 2);
    left = Math.min(Math.max(left, pad), window.innerWidth - w - pad);
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - pad) top = Math.max(pad, r.top - h - 6);
    toast.style.left = Math.round(left) + "px";
    toast.style.top = Math.round(top) + "px";
  }

  function show(btn, text) {
    ensureToast();
    toast.textContent = text;
    toast.hidden = false;
    place(btn);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 1800);
  }

  /* 老浏览器 / 非 https 页面的兜底：临时 textarea + execCommand("copy") */
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:-1000px;left:0;width:1px;height:1px;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return fallbackCopy(text); }
      );
    }
    return Promise.resolve(fallbackCopy(text));
  }

  /* 捕获阶段拦下：卡片手风琴、tab 切换、滑轨分页都别跟着动 */
  document.addEventListener("click", function (ev) {
    var btn = ev.target && ev.target.closest ? ev.target.closest(".url-copy") : null;
    if (!btn) return;
    ev.preventDefault();
    ev.stopPropagation();
    var url = (btn.getAttribute("data-copy") || btn.textContent || "").trim();
    if (!url) return;
    copy(url).then(function (ok) { show(btn, ok ? DONE : MANUAL); });
  }, true);
})();
