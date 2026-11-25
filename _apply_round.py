import json

p = "data/deals.json"
deals = json.load(open(p))
by = {x["id"]: x for x in deals}

# ---------- 1) Eskimo standing free trial: 500MB -> official 250MB ----------
e = by["eskimo-free-esim"]
e["title"] = "[全球]Eskimo免费eSIM：新用户250MB全球流量（126国/不过期）"
e["value"] = "250MB（约$2）"
e["value_num"] = 2
e["highlight"] = "注册时在「推荐或礼品代码」填FREE250MB，免费拿250MB全球流量，覆盖126个国家/地区，不过期、不要信用卡"
e["content"] = "旅行eSIM品牌Eskimo（新加坡Datapro）的免费试用：新用户下载App注册时在「推荐或礼品代码」处填FREE250MB，即可获250MB全球流量，覆盖126个以上国家/地区。官方免费页写明无需信用卡、装一次可在多国使用且流量不过期，适合落地用地图、打车和收消息。2026-11-26复核官方页只保留250MB档（此前500MB的FREE500MB已从官方页撤下，部分老账号仍可用）；更大的1GB礼品码见「Eskimo礼品码ESIMKART1GB」条目。"
e["conditions"] = "仅限Eskimo新用户；须在App注册时填码（漏填可于注册后24小时内补）；每账号一次；流量不过期，但账号连续约2年不用会被注销；不支持原生eSIM的国行手机需联系客服索要二维码，写入小白卡（APN选Singtel Postpaid、安装后勿删）。"
e["risk"] = "250MB只够应急（几小时导航与消息），不含通话；官方赠送档位已从500MB降到250MB，填码后以App内显示额度为准；国行机需另买小白卡/品牌eUICC卡，写卡失败要重来。"
e["source"] = "Eskimo 官方免费 eSIM 页（eskimo.travel/en/free-esim，2026-11-26 复核：FREE250MB／250MB／126国／无到期）"
e["last_verified"] = "2026-11-26"
e["verified"] = True

# ---------- 2) NEW: Eskimo 1GB gift code ----------
new1 = {
 "id": "eskimo-gift-1gb-code",
 "dedup_key": "eskimo|esim|global|gift-1gb",
 "title": "[全球]Eskimo礼品码ESIMKART1GB：新用户领1GB全球eSIM（2年有效，至11/30）",
 "brand": "Eskimo",
 "domain": "eskimo.travel",
 "category": "esim",
 "value": "1GB（约$7）",
 "value_num": 7,
 "cost": "真正免费",
 "highlight": "新用户注册时填礼品码 ESIMKART1GB，账户直接进 1GB 全球流量（约值 $7），不用买套餐、不绑卡",
 "regions": "[全球] 120+国家/地区（新加坡等个别国家不在覆盖内）；仅限新用户",
 "start": "",
 "end": "2026-11-30",
 "verified": True,
 "last_verified": "2026-11-26",
 "added": "2026-11-26",
 "content": "Eskimo的限时新手礼品码：新账号在App注册页（或注册后24小时内在Vouchers/Gifts页）填ESIMKART1GB，即到账1GB全球流量，不用付款、不绑卡。官方合作方Triple-A在2026-08-19公告写明新用户可领1GB全球eSIM（价值$7）、活动到2026-11-30；码页eSIMKart标注码有效期到2027-09-09，但设总兑换上限、可能提前关闭。2026-11-25新西兰Cheapies有实测：只需姓名+邮箱注册，App内填码即到账，数据约2年有效。",
 "conditions": "仅限Eskimo新用户；须在App注册时填码（已注册可在Vouchers/Gifts页补填），一账号一次；手机需支持eSIM且未锁网；覆盖国家以App内清单为准（新加坡不在内）；官方标注活动到2026-11-30，兑换总量有上限。",
 "steps": [
  "下载 Eskimo App（开发商 Datapro Technologies）并注册新账号（邮箱即可）",
  "在注册页的推荐／礼品码栏填 ESIMKART1GB；漏填就在注册后24小时内的 Vouchers/Gifts 页补填",
  "到 Data 页确认出现 1GB Global 流量卡",
  "支持 eSIM 的手机直接安装；国行机联系客服要二维码写入小白卡",
  "落地后把移动数据切到该 eSIM 并打开数据漫游"
 ],
 "url": "https://www.eskimo.travel/en/free-esim",
 "source": "Triple-A 官方合作公告（2026-08-19：新用户免费 1GB 全球 eSIM、价值 $7、至 2026-11-30）+ eSIMKart 礼品码页（码 ESIMKART1GB，标有效期 2027-09-09、设总兑换上限）+ Cheapies NZ 2026-11-25 实测帖（node/57972）",
 "source_url": "https://www.cheapies.nz/node/57972",
 "risk": "1GB 为一次性赠送、用完即止，不含通话；码有总兑换上限，可能提前失效；新加坡等个别国家不在覆盖内；需 eSIM 兼容且未锁网手机，国行机要另配可写卡。",
 "status": "active",
 "added_at": "2026-11-26T04:52:10+08:00",
 "kyc_level": "none",
 "vowifi": "n/a",
 "utility": 0,
 "platform_requirement": ["android", "ios"],
 "geo_restriction": ["GLOBAL"]
}

# ---------- 3) NEW: ElevenLabs startup grants ----------
new2 = {
 "id": "elevenlabs-startup-grants",
 "dedup_key": "elevenlabs|software|global|startup-grants",
 "title": "[全球]ElevenLabs创业资助：12个月Scale+3,300万字符（价值$5,500+，滚动申请）",
 "brand": "ElevenLabs",
 "domain": "elevenlabs.io",
 "category": "software",
 "value": "$5,500+（12个月Scale+33M字符）",
 "value_num": 5500,
 "cost": "真正免费",
 "highlight": "早期创业团队申请通过即得12个月Scale套餐+3,300万字符（官方称价值超$5,500），覆盖TTS、声音克隆与Agents，通常一周内出结果",
 "regions": "[全球] 线上申请；仅限员工少于25人的初创或小公司（代理商、咨询公司、中小企业不符）",
 "start": "",
 "end": "",
 "verified": True,
 "last_verified": "2026-11-26",
 "added": "2026-11-26",
 "content": "ElevenLabs Grants面向早期创业团队：通过后给12个月Scale套餐+3,300万字符（官方换算超过680小时Agents用量、价值$5,500以上），并附创始人社区活动与支持。要求有清晰的商业化路径和公司邮箱，不为一次性项目、campaign或面向18岁以下用户的产品发放；员工须少于25人，代理商、咨询公司与中小企业不可申请；每家公司限一份，付费自助用户可申请，企业版客户不行。滚动受理、一般一周内答复；额度用尽或满12个月自动转回Free。",
 "conditions": "需公司邮箱与明确变现方案；员工少于25人的初创/小公司；不接受一次性项目、代理商、咨询公司及面向未成年人的产品；每家公司限一次申请；额度不可转售套现；12个月到期或33M字符用尽即回Free档。",
 "steps": [
  "打开 elevenlabs.io/startup-grants，点 Apply 填写公司、产品与增长计划",
  "用公司邮箱提交，等待约一周的审核结果",
  "通过后额度自动打到申请所用账号的 Grant 套餐",
  "在控制台确认 Scale 套餐与 33M 字符已生效再开始接入 API"
 ],
 "url": "https://elevenlabs.io/startup-grants",
 "source": "ElevenLabs 官方 Grants 页（2026-11-26 复核：12 months Scale、33,000,000 characters、$5,500+ value、一周内答复、员工<25人）",
 "risk": "这是申请制资助而非人人可领，产品与团队不符会被拒；额度不可转售，用尽或期满自动降回 Free，正在跑的产品要提前规划续费。",
 "status": "active",
 "added_at": "2026-11-26T04:53:30+08:00",
 "kyc_level": "none",
 "utility": 0
}

deals.append(new1)
deals.append(new2)

for i in ["topcashback-uk-signup-10", "jpm-personal-investing-invest-1000-100", "doubao-work-30day-sub", "elevenlabs-black-friday-creator"]:
    x = by[i]
    x["last_verified"] = "2026-11-26"
    x["verified"] = True

with open(p, "w") as f:
    json.dump(deals, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("ok deals:", len(deals))
