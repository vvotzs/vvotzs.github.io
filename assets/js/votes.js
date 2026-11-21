/* 赞 / 踩：只拉一次票数填充显示，只乐观更新本卡数字，永不重排。
   契约见 docs/votes-api.md（schema 1）。 */
(function () {
  "use strict";

  var meta = document.querySelector('meta[name="dh-votes-base"]');
  var BASE = meta && meta.getAttribute("content");
  if (!BASE) return;

  var isEn = (document.documentElement.getAttribute("data-lang") || "zh") === "en";
  var LS_VID = "dh_vid";
  var LS_VOTES = "dh_votes";

  function randomVid() {
    var bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.prototype.map
      .call(bytes, function (b) {
        return ("0" + b.toString(16)).slice(-2);
      })
      .join("");
  }

  function readJson(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* 隐私模式 / 配额满：退化为单次会话内的乐观更新 */
    }
  }

  var vid = "";
  try {
    vid = localStorage.getItem(LS_VID) || "";
    if (!/^[0-9a-f]{32}$/.test(vid)) {
      vid = randomVid();
      localStorage.setItem(LS_VID, vid);
    }
  } catch (e) {
    vid = randomVid();
  }

  var myVotes = readJson(LS_VOTES, {}) || {};
  if (typeof myVotes !== "object" || Array.isArray(myVotes)) myVotes = {};

  var bars = Array.prototype.slice.call(document.querySelectorAll("[data-vote]"));
  if (!bars.length) return;

  var counts = {}; // id -> {up, down}

  function box(id) {
    return bars.filter(function (b) {
      return b.getAttribute("data-vote") === id;
    });
  }

  function setCount(id, up, down) {
    counts[id] = { up: Math.max(0, up), down: Math.max(0, down) };
    box(id).forEach(function (b) {
      var u = b.querySelector('[data-n="up"]');
      var d = b.querySelector('[data-n="down"]');
      if (u) u.textContent = String(counts[id].up);
      if (d) d.textContent = String(counts[id].down);
    });
  }

  /* 理由气泡的容器不再写进 HTML（首页 144 张卡就是 144 个空节点，DOM 数直接顶到 1.3 万
     上限），等真要显示理由时才建：只在 showWhy() 里调。 */
  function whyOf(bar) {
    var why = bar.querySelector(".vote-why");
    if (!why) {
      why = document.createElement("span");
      why.className = "vote-why";
      why.hidden = true;
      bar.appendChild(why);
    }
    return why;
  }

  function paintPressed(id) {
    var state = myVotes[id] || { v: 0, reason: "none" };
    box(id).forEach(function (b) {
      Array.prototype.forEach.call(b.querySelectorAll(".vb"), function (btn) {
        var v = Number(btn.getAttribute("data-v"));
        btn.setAttribute("aria-pressed", String(state.v === v));
      });
      var why = b.querySelector(".vote-why");
      if (why) {
        var open = state.v === -1 || (state.v === 1 && state.reason === "claimed");
        if (open) showWhy(b, state.v, state.reason);
        else {
          why.hidden = true;
          why.textContent = "";
        }
      }
    });
  }

  var LABELS = isEn
    ? { claimed: "Got it", useless: "Useless", expired: "Expired", inaccurate: "Inaccurate" }
    : { claimed: "已领到", useless: "没用", expired: "已失效", inaccurate: "信息不准" };

  function showWhy(bar, v, reason) {
    var why = whyOf(bar);
    if (!why) return;
    var keys = v === 1 ? ["claimed"] : ["useless", "expired", "inaccurate"];
    why.textContent = "";
    keys.forEach(function (key) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "vw" + (reason === key ? " on" : "");
      chip.setAttribute("data-reason", key);
      chip.textContent = LABELS[key];
      why.appendChild(chip);
    });
    why.hidden = false;
  }

  function optimistic(id, nextV) {
    var prev = myVotes[id] || { v: 0, reason: "none" };
    var c = counts[id] || { up: 0, down: 0 };
    var up = c.up;
    var down = c.down;
    if (prev.v === 1) up -= 1;
    if (prev.v === -1) down -= 1;
    if (nextV === 1) up += 1;
    if (nextV === -1) down += 1;
    setCount(id, up, down);
  }

  function post(id, v, reason, cb) {
    var body = JSON.stringify({
      schema: 1,
      type: "vote",
      id: id,
      vid: vid,
      v: v,
      reason: reason,
      lang: isEn ? "en" : "zh",
    });
    fetch(BASE, {
      method: "POST",
      mode: "cors",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: body,
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        cb(data && data.ok ? null : data, data);
      })
      .catch(function (err) {
        cb(err, null);
      });
  }

  function apply(id, v, reason, previous, beforeCounts) {
    if (v === 0) delete myVotes[id];
    else myVotes[id] = { v: v, reason: reason || "none" };
    writeJson(LS_VOTES, myVotes);
    paintPressed(id);
    post(id, v, reason || "none", function (err, data) {
      if (err || !data) {
        // 失败就退回投票前的状态与本卡数字，避免显示一个服务器没有的票
        if (previous) myVotes[id] = previous;
        else delete myVotes[id];
        writeJson(LS_VOTES, myVotes);
        paintPressed(id);
        if (beforeCounts) setCount(id, beforeCounts.up, beforeCounts.down);
        return;
      }
      if (typeof data.up === "number" && typeof data.down === "number") {
        setCount(id, data.up, data.down);
      }
    });
  }

  document.addEventListener("click", function (ev) {
    var chip = ev.target.closest ? ev.target.closest(".vote-why .vw") : null;
    if (chip) {
      var bar = chip.closest("[data-vote]");
      if (!bar) return;
      ev.preventDefault();
      var id = bar.getAttribute("data-vote");
      var state = myVotes[id] || { v: 0 };
      var reason = chip.getAttribute("data-reason");
      if (state.v !== 1 && state.v !== -1) return;
      myVotes[id] = { v: state.v, reason: reason };
      writeJson(LS_VOTES, myVotes);
      paintPressed(id);
      post(id, state.v, reason, function (err, data) {
        if (!err && data && typeof data.up === "number") setCount(id, data.up, data.down);
      });
      return;
    }

    var btn = ev.target.closest ? ev.target.closest(".vb") : null;
    if (!btn) return;
    var host = btn.closest("[data-vote]");
    if (!host) return;
    ev.preventDefault();
    var dealId = host.getAttribute("data-vote");
    var v = Number(btn.getAttribute("data-v"));
    if (v !== 1 && v !== -1) return;
    if (btn.getAttribute("aria-busy") === "true") return;
    var previous = myVotes[dealId] ? { v: myVotes[dealId].v, reason: myVotes[dealId].reason } : null;
    var nextV = previous && previous.v === v ? 0 : v;
    var beforeCounts = counts[dealId] ? { up: counts[dealId].up, down: counts[dealId].down } : null;
    optimistic(dealId, nextV);
    apply(dealId, nextV, "none", previous, beforeCounts);
    if (nextV === -1 || nextV === 1) showWhy(host, nextV, "none");
  });

  // 只拉一次票数；失败就保持「–」，不阻塞页面
  fetch(BASE + "?r=votes&_=" + Date.now(), { cache: "no-store" })
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (!data || data.schema !== 1 || !data.items) return;
      Object.keys(data.items).forEach(function (id) {
        var pair = data.items[id];
        if (Array.isArray(pair) && pair.length >= 2) {
          counts[id] = { up: Number(pair[0]) || 0, down: Number(pair[1]) || 0 };
        }
      });
      bars.forEach(function (bar) {
        var id = bar.getAttribute("data-vote");
        var c = counts[id] || { up: 0, down: 0 };
        var u = bar.querySelector('[data-n="up"]');
        var d = bar.querySelector('[data-n="down"]');
        if (u) u.textContent = String(c.up);
        if (d) d.textContent = String(c.down);
        paintPressed(id);
      });
    })
    .catch(function () {
      /* 离线 / GAS 不可达：票数保持「–」，按钮仍可点（乐观更新） */
    });
})();
