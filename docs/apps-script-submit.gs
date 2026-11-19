/**
 * 羊毛情报局 / Deal Hunter — 投稿表单接收端（Google Apps Script Web App）
 *
 * 线上部署：script.google.com 项目「Deal Hunter Submit」→ 部署 → 管理部署 → 编辑（铅笔）
 *           → 版本选「新版本」→ 部署。原地升级，/exec URL 不变，不会中断直邮。
 *
 * 前端（assets/js/app.js）用 fetch(no-cors) POST form-urlencoded 到这里，字段：
 *   name, url, region, notes, lang, hp_x7, elapsed_ms
 *   hp_x7      蜜罐：真人看不到也碰不到，有值即机器人
 *   elapsed_ms 弹窗打开 → 点提交的毫秒数；未传、非数字、或小于 MIN_ELAPSED_MS 一律拒绝
 *
 * 服务端防护（不信任前端）：
 *   1) hp_x7 非空 → 静默成功，不发信
 *   2) elapsed_ms 缺失 / 非数字 / 过小 → 静默成功，不发信（不传参数绕不过去）
 *   3) 必填校验 name / url
 *   4) LockService 串行化：限流计数与去重缓存不会并发超发
 *   5) 每分钟全场最多 MAX_PER_MINUTE 条；MailApp 日额度提前检查
 *   6) 同一链接 30 分钟内只发一次，key 用 URL 的 SHA-256（不截断）
 *   7) 先 MailApp.sendEmail 成功、再写去重缓存：发信失败后用户可以立刻重试
 */

var OWNER_EMAIL = 'vvotzs@gmail.com';
var MIN_ELAPSED_MS = 1500;      /* 少于 1.5 秒：基本是脚本 */
var MAX_PER_MINUTE = 6;         /* 全场每分钟最多处理 6 条（防刷爆 MailApp 日额度） */
var DEDUPE_SECONDS = 1800;      /* 同一链接 30 分钟内只发一次 */
var MAX_NAME = 80;
var MAX_URL = 500;
var MAX_REGION = 60;
var MAX_NOTES = 800;

function doPost(e) {
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

/** GET 只是给浏览器 / 健康检查一个不报错的白页，不暴露任何东西。 */
function doGet() {
  return json({ ok: true });
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
