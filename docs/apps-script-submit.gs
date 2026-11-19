/**
 * 羊毛情报局 / Deal Hunter — 投稿表单接收端（Google Apps Script 参考实现）
 *
 * 用途：页面上的原生 <dialog> 表单用 fetch(no-cors) POST 到这里，脚本用 MailApp 把投稿
 *       发到 vvotzs@gmail.com。不需要第三方表单服务，也不占它的额度。
 *
 * 这份文件是留档 / 重建用的完整版，**不是**线上那份的自动同步：
 *   - 线上 Web App 仍在跑旧参数（蜜罐字段名 website、没有 elapsed_ms），本次没有重部署，
 *     以免换版本时中断现有直邮；等下次要动线上脚本时按这份整体替换即可。
 *   - 页面已经会带 hp_x7 与 elapsed_ms，旧脚本读不到这两个参数也不会出错，只是少两层拦截。
 *
 * 部署：Apps Script 新建项目 → 粘贴本文件 → 部署 → 类型「Web 应用」→
 *       执行身份「我」/ 访问权限「任何人」→ 把 /exec 地址写回 scripts/build_site.py 的
 *       SUBMIT_ENDPOINT 后重建站点。
 *
 * 与前端 app.js 的约定（改动时两边一起看）：
 *   name, url, region, notes, lang, hp_x7, elapsed_ms（全部 form-urlencoded）
 *   hp_x7     蜜罐：真人看不到、也碰不到，有值即机器人
 *   elapsed_ms 弹窗打开 → 点提交的毫秒数，真人手填不会小于 1200
 */

var OWNER_EMAIL = 'vvotzs@gmail.com';
var MIN_ELAPSED_MS = 1200;      // 少于 1.2 秒：基本是脚本
var MAX_PER_MINUTE = 6;         // 全场每分钟最多处理 6 条（防脚本刷爆 MailApp 日额度）
var MAX_NAME = 80;
var MAX_URL = 500;
var MAX_REGION = 60;
var MAX_NOTES = 800;

function doPost(e) {
  var p = (e && e.parameter) || {};

  var name = clip(p.name, MAX_NAME);
  var url = clip(p.url, MAX_URL);
  var region = clip(p.region, MAX_REGION);
  var notes = clip(p.notes, MAX_NOTES, true);   // 说明允许换行
  var lang = p.lang === 'en' ? 'en' : 'zh';
  var hp = (p.hp_x7 || '').toString();
  var elapsed = parseInt(p.elapsed_ms, 10);

  // 1) 蜜罐：有值就当垃圾，回一个「成功」让脚本以为得手，实际不发信。
  if (hp) {
    Logger.log('honeypot hit: %s', hp.slice(0, 40));
    return json({ ok: true });
  }

  // 2) 耗时：弹窗刚打开就提交，不是人填的。
  if (!isNaN(elapsed) && elapsed < MIN_ELAPSED_MS) {
    Logger.log('too fast: %sms', elapsed);
    return json({ ok: true });
  }

  // 3) 必填校验（前端也校验一次，这里不相信前端）。
  if (!name || !url) return json({ ok: false, error: 'missing_fields' });

  // 4) 每分钟限流：CacheService 共享、无状态，重启也不丢计数。
  var cache = CacheService.getScriptCache();
  var bucket = 'ydj_rl_' + Math.floor(Date.now() / 60000);
  var used = parseInt(cache.get(bucket), 10) || 0;
  if (used >= MAX_PER_MINUTE) {
    Logger.log('rate limited: %s in this minute', used);
    return json({ ok: false, error: 'rate_limited' });
  }
  cache.put(bucket, String(used + 1), 120);

  // 5) MailApp 日额度：用完就别再尝试，免得抛异常把请求变成 500。
  if (MailApp.getRemainingDailyQuota() < 1) {
    Logger.log('MailApp quota exhausted');
    return json({ ok: false, error: 'mail_quota' });
  }

  // 6) 同一链接 30 分钟内只发一次（连点 / 用户重复提交）。
  var dedupe = 'ydj_dup_' + Utilities.base64EncodeWebSafe(url).slice(0, 120);
  if (cache.get(dedupe)) return json({ ok: true, dup: true });
  cache.put(dedupe, '1', 1800);

  var subject = '[投稿] ' + name + (region ? ' · ' + region : '');
  var body = [
    '名称: ' + name,
    '链接: ' + url,
    '地区: ' + (region || '-'),
    '页面语言: ' + lang,
    '停留: ' + (isNaN(elapsed) ? '-' : elapsed + ' ms'),
    '',
    '亮点与门槛:',
    notes || '-',
    '',
    '-- 来自 ' + (lang === 'en' ? '/en/' : '/') + ' 投稿弹窗'
  ].join('\n');

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

  return json({ ok: true });
}

/** GET 只是给浏览器 / 健康检查一个不报错的白页，不暴露任何东西。 */
function doGet() {
  return json({ ok: true });
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
