/**
 * 羊毛情报局 / Deal Hunter — 投稿接收 + 赞/踩计数（Google Apps Script Web App）
 *
 * 线上部署：script.google.com 项目「Deal Hunter Submit」→ 部署 → 管理部署 → 编辑（铅笔）
 *           → 版本选「新版本」→ 部署。原地升级，/exec URL 不变，不会中断投稿与投票。
 *
 * 同一入口两种用途：
 *   1) 投稿（原有，100% 不变）：form-urlencoded POST，字段
 *      name, url, region, notes, lang, hp_x7, elapsed_ms
 *   2) 赞/踩（schema 1，契约见 docs/votes-api.md）：
 *      GET  /exec?r=votes                     → {schema,generated_at,items:{id:[up,down]}}
 *      POST text/plain JSON {type:"vote",...} → {ok:true,up:n,down:n}
 *      GET  /exec?r=export&token=<TOKEN>      → 只追加日志的纯文本行
 *
 * 投票存储（零新增授权）：
 *   v:<id>         每条优惠一个键，值 {"u":12,"d":1}（单值上限 9KB，绝不把全站塞一个键）
 *   p:<id>:<vid>   这个浏览器在此条目的上一票 1 / -1（撤销时删除）
 *   log_0..log_n   事件日志，每块 ≤8KB，只追加
 *   EXPORT_TOKEN   导出令牌（不在代码与仓库里，见脚本属性）
 */

var OWNER_EMAIL = 'vvotzs@gmail.com';
var MIN_ELAPSED_MS = 1500;      /* 少于 1.5 秒：基本是脚本 */
var MAX_PER_MINUTE = 6;         /* 全场每分钟最多处理 6 条（防刷爆 MailApp 日额度） */
var DEDUPE_SECONDS = 1800;      /* 同一链接 30 分钟内只发一次 */
var MAX_NAME = 80;
var MAX_URL = 500;
var MAX_REGION = 60;
var MAX_NOTES = 800;

/* --- 投票常量 --- */
var VOTE_SCHEMA = 1;
var VOTE_MAX_PER_10MIN = 30;    /* 单个 vid 10 分钟最多 30 次 */
var VOTE_RATE_WINDOW = 600;
var LOG_CHUNK_MAX = 7600;       /* 单块 JSON 字符数上限，留足 9KB 字节余量 */
var MAX_VOTE_ID = 64;
var VOTE_REASONS = { none: 1, claimed: 1, useless: 1, expired: 1, inaccurate: 1 };

function doPost(e) {
  /* 投票走 text/plain JSON；投稿仍是 form-urlencoded，两条路互不影响。 */
  var vote = votePayload(e);
  if (vote) return handleVote(vote);

  var p = params(e);
  var name = clip(p.name, MAX_NAME);
  var url = clip(p.url, MAX_URL);
  var region = clip(p.region, MAX_REGION);
  var notes = clip(p.notes, MAX_NOTES, true);
  var lang = p.lang === 'en' ? 'en' : 'zh';
  var hp = String(p.hp_x7 == null ? '' : p.hp_x7).trim();
  var elapsedRaw = p.elapsed_ms;
  var elapsed = parseInt(elapsedRaw, 10);

  /* 1) 蜜罐：有值就当机器人，回「成功」让它以为得手，实际不发信。 */
  if (hp) {
    Logger.log('honeypot hit: %s', hp.slice(0, 40));
    return json({ ok: true });
  }

  /* 2) 停留时长：未传、非数字、或小于阈值都拦下来（旧版只在传了才判断，不传即可绕过）。 */
  if (elapsedRaw == null || String(elapsedRaw) === '' || isNaN(elapsed) || elapsed < MIN_ELAPSED_MS) {
    Logger.log('elapsed rejected: %s', elapsedRaw);
    return json({ ok: true });
  }

  /* 3) 必填校验（前端也校验一次，这里不相信前端）。 */
  if (!name || !url) return json({ ok: false, error: 'missing_fields' });

  /* 4) 并发锁：限流计数与去重缓存必须串行，否则并发时会超发。 */
  var lock = LockService.getScriptLock();
  var locked = false;
  try {
    locked = lock.tryLock(10000);
  } catch (err) {
    locked = false;
  }
  if (!locked) {
    Logger.log('lock busy');
    return json({ ok: false, error: 'busy' });
  }

  try {
    var cache = CacheService.getScriptCache();

    /* 5) 每分钟限流：CacheService 共享、无状态，重启也不丢计数。 */
    var bucket = 'ydj_rl_' + Math.floor(Date.now() / 60000);
    var used = parseInt(cache.get(bucket), 10) || 0;
    if (used >= MAX_PER_MINUTE) {
      Logger.log('rate limited: %s in this minute', used);
      return json({ ok: false, error: 'rate_limited' });
    }
    cache.put(bucket, String(used + 1), 120);

    /* MailApp 日额度：用完就别再尝试，免得抛异常把请求变成 500。 */
    if (MailApp.getRemainingDailyQuota() < 1) {
      Logger.log('MailApp quota exhausted');
      return json({ ok: false, error: 'mail_quota' });
    }

    /* 6) 同一链接 30 分钟内只发一次（连点 / 用户重复提交）。key 用完整 URL 的 SHA-256，不截断。 */
    var dedupe = 'ydj_dup_' + sha256(url);
    if (cache.get(dedupe)) {
      Logger.log('duplicate: %s', url);
      return json({ ok: true, dup: true });
    }

    var subject = '[投稿] ' + name + (region ? ' · ' + region : '');
    var body = [
      '名称: ' + name,
      '链接: ' + url,
      '地区: ' + (region || '-'),
      '页面语言: ' + lang,
      '停留: ' + elapsed + ' ms',
      '',
      '亮点与门槛:',
      notes || '-',
      '',
      '-- 来自 ' + (lang === 'en' ? '/en/' : '/') + ' 投稿弹窗'
    ].join('\n');

    /* 7) 先发信，成功后再写去重标记：发信失败不会把用户锁在 30 分钟冷却里。 */
    try {
      MailApp.sendEmail({
        to: OWNER_EMAIL,
        subject: subject,
        body: body,
        name: 'Deal Hunter · 投稿'
      });
    } catch (err) {
      Logger.log('send failed: %s', err);
      return json({ ok: false, error: 'send_failed' });
    }
    cache.put(dedupe, '1', DEDUPE_SECONDS);
    Logger.log('sent: %s', url);
    return json({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

/** GET：?r=votes 读票数；?r=export 导日志；其余给浏览器 / 健康检查一个不报错的白页。 */
function doGet(e) {
  var r = e && e.parameter ? e.parameter.r : '';
  if (r === 'votes') return votesJson();
  if (r === 'export') return exportLog(e);
  return json({ ok: true });
}

/* ------------------------------------------------------------------ 票数 */

function votesJson() {
  var props = PropertiesService.getScriptProperties().getProperties();
  var items = {};
  Object.keys(props).forEach(function (key) {
    if (key.indexOf('v:') !== 0) return;
    var pair = parseCount(props[key]);
    if (pair) items[key.slice(2)] = [pair.u, pair.d];
  });
  return json({
    schema: VOTE_SCHEMA,
    generated_at: new Date().toISOString(),
    items: items
  });
}

function parseCount(raw) {
  if (!raw) return { u: 0, d: 0 };
  try {
    var j = JSON.parse(raw);
    return { u: Math.max(0, parseInt(j.u, 10) || 0), d: Math.max(0, parseInt(j.d, 10) || 0) };
  } catch (err) {
    return { u: 0, d: 0 };
  }
}

function votePayload(e) {
  if (!e || !e.postData || !e.postData.contents) return null;
  var raw = String(e.postData.contents);
  if (raw.charAt(0) !== '{') return null;
  try {
    var j = JSON.parse(raw);
    return j && j.type === 'vote' ? j : null;
  } catch (err) {
    return null;
  }
}

function handleVote(payload) {
  var id = String(payload.id == null ? '' : payload.id).trim();
  var vid = String(payload.vid == null ? '' : payload.vid).trim().toLowerCase();
  var v = parseInt(payload.v, 10);
  var reason = String(payload.reason == null ? 'none' : payload.reason);
  var lang = payload.lang === 'en' ? 'en' : 'zh';

  if (parseInt(payload.schema, 10) !== VOTE_SCHEMA) return json({ ok: false, error: 'bad_body' });
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) return json({ ok: false, error: 'bad_id' });
  if (!/^[0-9a-f]{32}$/.test(vid)) return json({ ok: false, error: 'bad_vid' });
  if (v !== 1 && v !== -1 && v !== 0) return json({ ok: false, error: 'bad_vote' });
  if (!VOTE_REASONS[reason]) return json({ ok: false, error: 'bad_reason' });

  var lock = LockService.getScriptLock();
  var locked = false;
  try {
    locked = lock.tryLock(10000);
  } catch (err) {
    locked = false;
  }
  if (!locked) return json({ ok: false, error: 'busy' });

  try {
    /* vid 限流：10 分钟 30 次；CacheService 无状态，重启不丢。 */
    var cache = CacheService.getScriptCache();
    var rlKey = 'v_rl_' + vid;
    var used = parseInt(cache.get(rlKey), 10) || 0;
    if (used >= VOTE_MAX_PER_10MIN) return json({ ok: false, error: 'rate_limited' });
    cache.put(rlKey, String(used + 1), VOTE_RATE_WINDOW);

    var props = PropertiesService.getScriptProperties();
    var countKey = 'v:' + id;
    var prevKey = 'p:' + id + ':' + vid;
    var count = parseCount(props.getProperty(countKey));
    var prevRaw = props.getProperty(prevKey);
    var prev = prevRaw === '1' ? 1 : prevRaw === '-1' ? -1 : 0;

    if (prev === v) {
      /* 幂等：连点同一按钮不重复计数 */
      return json({ ok: true, up: count.u, down: count.d });
    }

    if (prev === 1) count.u = Math.max(0, count.u - 1);
    if (prev === -1) count.d = Math.max(0, count.d - 1);
    if (v === 1) count.u += 1;
    if (v === -1) count.d += 1;

    props.setProperty(countKey, JSON.stringify({ u: count.u, d: count.d }));
    if (v === 0) props.deleteProperty(prevKey);
    else props.setProperty(prevKey, String(v));

    appendLog([new Date().toISOString(), id, vid, v, reason, lang, VOTE_SCHEMA]);
    return json({ ok: true, up: count.u, down: count.d });
  } catch (err) {
    Logger.log('vote write failed: %s', err);
    return json({ ok: false, error: 'write_failed' });
  } finally {
    lock.releaseLock();
  }
}

/** 只追加的事件日志：log_0、log_1…，每块 ≤ LOG_CHUNK_MAX 字符。 */
function appendLog(line) {
  var props = PropertiesService.getScriptProperties();
  var idx = 0;
  var key = 'log_0';
  var raw = props.getProperty(key);
  while (raw) {
    var parsed = safeParse(raw);
    if (parsed && parsed.length) {
      var asJson = JSON.stringify(parsed.concat([line]));
      if (asJson.length <= LOG_CHUNK_MAX) {
        props.setProperty(key, asJson);
        return;
      }
      idx += 1;
      key = 'log_' + idx;
      raw = props.getProperty(key);
      continue;
    }
    break;
  }
  props.setProperty(key, JSON.stringify([line]));
}

function safeParse(raw) {
  try {
    var j = JSON.parse(raw);
    return Array.isArray(j) ? j : null;
  } catch (err) {
    return null;
  }
}

function exportLog(e) {
  var token = e && e.parameter ? String(e.parameter.token || '') : '';
  var expected = PropertiesService.getScriptProperties().getProperty('EXPORT_TOKEN');
  if (!expected || token !== expected) return json({ ok: false, error: 'forbidden' });
  var props = PropertiesService.getScriptProperties().getProperties();
  var lines = [];
  Object.keys(props)
    .filter(function (k) {
      return /^log_\d+$/.test(k);
    })
    .sort(function (a, b) {
      return parseInt(a.slice(4), 10) - parseInt(b.slice(4), 10);
    })
    .forEach(function (k) {
      var arr = safeParse(props[k]);
      if (arr) arr.forEach(function (row) { lines.push(JSON.stringify(row)); });
    });
  return ContentService.createTextOutput(lines.join('\n')).setMimeType(ContentService.MimeType.TEXT);
}

/** 一次性设置导出令牌（在编辑器里手动运行；返回值只出现在执行日志里）。 */
function setupExportToken() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('EXPORT_TOKEN');
  if (!token) {
    token = Utilities.getUuid().replace(/-/g, '');
    props.setProperty('EXPORT_TOKEN', token);
  }
  Logger.log('EXPORT_TOKEN=' + token);
  return token;
}

/** form-urlencoded 走 e.parameter；万一有 JSON 体（手工测试）也兼容一下。 */
function params(e) {
  var p = (e && e.parameter) || {};
  var keys = ['name', 'url', 'region', 'notes', 'lang', 'hp_x7', 'elapsed_ms'];
  if (e && e.postData && e.postData.contents && (!p.name || !p.url)) {
    try {
      var j = JSON.parse(e.postData.contents);
      keys.forEach(function (k) {
        if (!p[k] && j[k] != null) p[k] = String(j[k]);
      });
    } catch (err) {}
  }
  return p;
}

/** 完整 URL 的 SHA-256（hex），用作去重 key。 */
function sha256(text) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8);
  return bytes.map(function (b) {
    var v = (b < 0 ? b + 256 : b).toString(16);
    return v.length === 1 ? '0' + v : v;
  }).join('');
}

function clip(v, max, keepNewlines) {
  var s = (v == null ? '' : String(v)).replace(/\r\n?/g, '\n');
  if (!keepNewlines) s = s.replace(/\s+/g, ' ');
  return s.trim().slice(0, max);
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
