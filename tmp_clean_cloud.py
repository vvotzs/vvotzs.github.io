#!/usr/bin/env python3
"""合规改写：删除 cloud 条目中的代理/节点/隧道教程表述；并补录 Waifly / Wispbyte 免费面板机。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DP = ROOT / "data" / "deals.json"
EP = ROOT / "data" / "deals_en.json"

ZH = {
    "bot-hosting-net-free-panel": {
        "highlight": "免信用卡的免费容器：256MB 内存、25% CPU、512MB 存储、1 个部署，支持 Node.js / Python / Go / Rust 等任意运行时，给自定义端口 + 静态 IP 与免费 HTTPS 子域名，官方写明不休眠",
        "content": "bot-hosting.net 是给 Discord / Telegram 机器人与小型服务用的网页面板主机，免费档是少见的「免绑卡 + 可跑任意运行时 + 不休眠」组合：256MB 内存、25% CPU、512MB 存储、1 个部署，资源按「池子」发放——同一档额度可以在自己的多个部署之间自行分配。\n\n运行时支持很宽：Node、Python、Java、PHP、Go、Rust、C++、Lua、Bun 都能起，可一键装静态站 / PHP 站、Lavalink、Uptime Kuma；部署支持 GitHub 拉取、ZIP 上传与 bh deploy CLI。每个部署给 1 个端口与静态 IP，另送免费 HTTPS 子域名，环境变量、日志、控制台与崩溃自动重启都有。\n\n免费档的代价有两条：每 4 天必须在面板手动续期一次，忘了就停服；免费面板带广告（付费档才去广告）。官方文档 2026-11-17 说明新版面板把免费与付费容量分区，且因成本原因「每个用户只能建 1 台免费服务器」，旧面板即将下线。\n\n适合什么：Discord / Telegram 机器人、Webhook 接收端、小型 REST API、定时抓取脚本、静态或 PHP 展示站。300MB 以下的小进程够用，别指望跑构建型任务或大内存应用。",
        "conditions": "免费档：256MB 内存 / 25% CPU / 512MB 存储 / 1 个部署，免信用卡；每 4 天在面板手动续期一次，逾期停服；每人只能建 1 台免费服务器；免费面板带广告；支持 Node / Python / Go / Rust 等运行时与自定义端口；禁止 self-bot 等违反平台条款的用途。",
        "risk": "每 4 天手动续期，忘记就停服；只有 1 台免费服务器且免费面板带广告；256MB 内存跑稍重的应用会 OOM 被杀；官方已说明免费容量因成本下调，随时可能再缩；滥用或违反条款会封号。",
        "steps": [
            "打开 bot-hosting.net，注册账号（免费档不需要信用卡）",
            "在面板新建部署，选运行时（Node.js / Python 等），从 GitHub、ZIP 或 CLI 上传代码",
            "设置启动命令与环境变量，确认分配的端口、静态 IP 与免费 HTTPS 子域名",
            "每 4 天回面板点一次续期，避免停服",
        ],
        "source": "bot-hosting.net 官方定价页与文档（2026-11-21 核验：免费档资源、每 4 天手动续期、任意运行时与自定义端口、新版面板免费容量说明）+ 官方 llms.txt + Space-Node 免费机器人主机横评（2026-11-03）",
    },
    "katabump-free-pterodactyl-panel": {
        "highlight": "Pterodactyl（翼龙）系面板主机，免费档 308MB 内存、716MB NVMe、25% CPU，免信用卡；支持 Node.js / Python 常驻、SFTP、网页 ZIP 上传与 git clone，启动命令可自行修改",
        "content": "KataBump 是 Pterodactyl（翼龙）面板的免费托管：免费档 308MB 内存、716MB NVMe 存储、25% CPU、I/O 100，免信用卡，官方 FAQ 直接写「basic hosting plan is entirely free」。\n\n能做什么：Node.js（package.json 必填、index.js 为入口）与 Python（requirements.txt + main.py）都支持，首次启动自动 npm install / pip install；文件可以网页拖拽 ZIP（单文件 100MB 上限）、SFTP（地址形如 sftp://fr-node-xx.katabump.fr:2022，账号是服务器 ID）或在控制台 git clone；环境变量、实时日志、开机自启都有。Startup 页可以随时换 Node / Python 版本、改入口文件与额外依赖，也能在两种运行时之间切换。\n\n续期规则要记清：免费服务器每 4 天手动续一次（只能在到期前 2 天内点），过期立刻停服，停服 1 天后文件永久删除且不可恢复；付费档自动续期。数据库只有 SQLite 免费，MariaDB 要付费档，但可以外接 MongoDB Atlas 之类。\n\n适合什么：Discord 机器人、定时任务、Webhook 接收端、小型 API 与静态演示。308MB 内存是硬上限，构建型任务和重负载应用跑不动。",
        "conditions": "免费档：308MB 内存 / 716MB NVMe / 25% CPU，免信用卡；每 4 天手动续期（到期前 2 天内），逾期停服、停服 1 天后文件永久删除；仅 SQLite 免费，MariaDB 需付费档；禁止 self-bot 等违反平台条款的用途；支持 Node.js / Python 与自定义启动命令。",
        "risk": "续期窗口很短（到期前 2 天内才能点），忘记就停服并在 1 天后被永久删除，数据不可恢复；308MB 内存跑重一点的应用会 OOM 并被自动重启；免费档没有备份与 MariaDB；节点多在法国，晚高峰延迟一般；滥用或违反条款会封号。",
        "steps": [
            "在 dashboard.katabump.com 注册（免费档不需要信用卡），新建一台免费服务器",
            "选 Node.js 或 Python 运行时，上传 package.json + index.js（或 requirements.txt + main.py），也可用 SFTP 或控制台 git clone",
            "到 control.katabump.com 的 Startup 页确认入口文件与启动命令",
            "启动后在控制台看实时日志；每 4 天在面板点一次 Renew now 保号",
        ],
        "source": "KataBump 官方文档 FAQ / Plans / Renew Your Server（2026-11-21 核验：免费档 308MB / 716MB / 25%、每 4 天续期、停服 1 天后删除、Node 与 Python 支持）",
    },
}

EN = {
    "bot-hosting-net-free-panel": {
        "highlight": "A free container with no credit card: 256MB RAM, 25% CPU, 512MB storage and one deployment, any runtime from Node.js and Python to Go and Rust, with a custom port, static IP and free HTTPS subdomain, and no sleep mode according to the official page",
        "content": "bot-hosting.net is a web-panel host for Discord and Telegram bots and small services, and its free tier is a rare mix: no card, any runtime, and no sleep timer. You get 256MB RAM, 25% CPU, 512MB storage and one deployment, and the resources are a pool you split across your own deployments.\n\nRuntime support is broad: Node, Python, Java, PHP, Go, Rust, C++, Lua and Bun all start, with one-click static and PHP sites, Lavalink and Uptime Kuma. Deployment works from GitHub, a ZIP upload or the bh deploy CLI, and each deployment gets one port, a static IP and a free HTTPS subdomain, alongside environment variables, logs, a console and auto-restart on crash.\n\nThe free tier costs you two things: a manual renewal in the panel every four days, without which the service stops, and ads in the free panel, which paid plans remove. Official docs dated 17 November explain that the new panel partitions capacity between free and paid servers and that, because of cost, each user can now create only one free server; the legacy panel is being retired.\n\nWhat fits: Discord and Telegram bots, webhook receivers, small REST APIs, scheduled scrapers and static or PHP showcase sites. Processes under 300MB are fine; do not expect it to run build steps or memory-heavy applications.",
        "conditions": "Free tier: 256MB RAM, 25% CPU, 512MB storage and one deployment, no credit card; renew manually in the panel every four days or the service stops; one free server per user; ads in the free panel; Node, Python, Go and Rust runtimes with custom ports supported; self-bots and other terms-violating uses are prohibited.",
        "risk": "Renewal every four days is manual and forgetting it stops the service; only one free server and the free panel carries ads; 256MB runs out on anything heavier and the process is killed; the official docs already cut free capacity for cost, so it can shrink again; abuse or terms violations lead to a ban.",
        "steps": [
            "Open bot-hosting.net and register, since the free tier needs no credit card",
            "Create a deployment in the panel, pick a runtime such as Node.js or Python, and upload code from GitHub, a ZIP or the CLI",
            "Set the start command and environment variables, and note the assigned port, static IP and free HTTPS subdomain",
            "Return to the panel every four days to renew so the service keeps running",
        ],
        "source": "bot-hosting.net official pricing page and docs (checked 21 November 2026: free tier resources, four-day manual renewal, any runtime and custom ports, new-panel free capacity notes) + official llms.txt + Space-Node free bot hosting comparison (3 November 2026)",
    },
    "katabump-free-pterodactyl-panel": {
        "highlight": "A Pterodactyl panel host whose free tier gives 308MB RAM, 716MB NVMe and 25% CPU with no credit card; Node.js and Python processes run long, with SFTP, web ZIP uploads, git clone and an editable start command",
        "content": "KataBump hosts Pterodactyl panels for free: the free tier is 308MB RAM, 716MB NVMe storage, 25% CPU and I/O 100, with no credit card, and the official FAQ states plainly that the basic hosting plan is entirely free.\n\nWhat it runs: Node.js with a required package.json and an index.js entry point, or Python with requirements.txt and main.py, installing dependencies with npm install or pip install on first start. Files go in by web ZIP upload (100MB per file), SFTP (at an address like sftp://fr-node-xx.katabump.fr:2022, with the server ID as the username) or git clone from the console, and environment variables, live logs and auto-start are included. The Startup tab lets you change the Node or Python version, the entry file and extra packages, and switch between the two runtimes at any time.\n\nRenewal needs care: free servers must be renewed by hand every four days, and only within the two days before expiry; a lapsed server is suspended at once and its files are permanently deleted one day later with no recovery. Paid plans renew automatically. SQLite is free while MariaDB needs a paid plan, though external databases such as MongoDB Atlas can be attached.\n\nWhat fits: Discord bots, scheduled jobs, webhook receivers, small APIs and static demos. The 308MB ceiling is hard, so builds and heavy applications do not run here.",
        "conditions": "Free tier: 308MB RAM, 716MB NVMe and 25% CPU with no credit card; renew by hand every four days, within the two days before expiry, or the server is suspended and its files are deleted one day later; SQLite only, with MariaDB on paid plans; self-bots and other terms-violating uses are prohibited; Node.js and Python with an editable start command.",
        "risk": "The renewal window is only the two days before expiry, and missing it suspends the server and deletes the files a day later with no recovery; 308MB runs out on heavier applications and triggers automatic restarts; free plans have no backups and no MariaDB; most nodes are in France, so latency is mediocre at peak times; abuse or terms violations lead to a ban.",
        "steps": [
            "Register at dashboard.katabump.com without a card and create a free server",
            "Choose the Node.js or Python runtime and upload package.json plus index.js, or requirements.txt plus main.py, over SFTP or with git clone",
            "On the Startup tab at control.katabump.com confirm the entry file and start command",
            "Start the server and watch the live log; click Renew now in the panel every four days to keep it alive",
        ],
        "source": "KataBump official docs FAQ, Plans and Renew Your Server (checked 21 November 2026: free tier 308MB / 716MB / 25%, four-day renewal, deletion one day after suspension, Node and Python support)",
    },
}

NEW = [
    {
        "id": "waifly-free-nodejs-panel",
        "title": "[全球] Waifly 永久免费 Node.js 面板机：300MB 内存 + 1GB 存储 + 1 个 MySQL",
        "brand": "Waifly",
        "domain": "waifly.com",
        "category": "cloud",
        "value": "300MB 内存 + 1GB 存储 + MySQL，永久 €0（付费 €4/月起）",
        "value_num": 0,
        "cost": "真正免费",
        "highlight": "法国巴黎的 Pterodactyl 面板主机，免费档永久 €0、免绑卡、不限时长：300MB 内存、30% vCPU、1GB 存储、1 个 MySQL 库与 1 个端口，有实时控制台、网页文件管理、SFTP、计划任务与备份；服务器离线满 3 天会被暂停",
        "regions": "[全球] 网上面板注册（dash.waifly.com），节点在法国巴黎 FR1 / FR2；免费档不需要信用卡，一人一账号",
        "start": "",
        "end": "",
        "content": "Waifly 是法国团队做的免费 Node.js 托管，官方写得很清楚：免费档是永久 €0，不是试用，没有到期日、不需要信用卡、也没有每月时长限制，进程可以一直跑。\n\n给的东西：300MB 内存、30% 单核 CPU、1GB 存储、1 个 MySQL 数据库、1 个端口，容器跑在 Pterodactyl 面板下（Proxmox + Docker），所以没有 root、没有 SSH，但有实时控制台、带编辑器的网页文件管理、SFTP、计划任务与备份，还有各档都含的 DDoS 防护。\n\n怎么用：在 dash.waifly.com 注册，进 Servers 建一台服务器，选 NodeJS Egg 与巴黎的 FR1 / FR2 节点；上传项目时只要带 package.json，启动时会自动 npm install；在 Startup 页把入口指向主文件（node index.js 或 npm start），端口以环境变量提供，别硬编码。想绑自己的域名，把 A 记录指向服务器 IP 后在域名管理页登记，系统会自动生成 Nginx 反向代理。\n\n能装什么：Discord 机器人、Express / Fastify 的 REST API、Telegram 机器人、定时抓取、Webhook 接收端、Nginx 后面的静态站都在 300MB 内跑得动（Node 本身约占 40–50MB）。跑不动的：在服务器上构建 Next.js、Puppeteer / 无头 Chrome、音视频转码，这些得上 €4/月的 Nano 档。\n\n风控与规则：反滥用规则是「服务器离线超过 3 天自动暂停」；一人只能一个账号，官方说每 30 分钟会做一次自动检查，重复注册开小号会被处理。",
        "conditions": "免费档：300MB 内存 / 30% vCPU / 1GB 存储 / 1 个 MySQL / 1 个端口，永久 €0、免信用卡、不限时长；服务器离线超过 3 天会被自动暂停；一人一账号，禁止多开；无 root 与 SSH，只能通过面板、SFTP 与 MySQL 管理。",
        "steps": [
            "在 dash.waifly.com 注册账号（免费档无需信用卡）",
            "进 Servers 点 Create，选 NodeJS Egg 与 FR1 / FR2 节点，免费额度自动套用",
            "上传项目（带 package.json），在 Startup 页设置入口文件与启动命令",
            "启动后在实时控制台看 npm install 与运行日志；保持服务器在线，离线 3 天会被暂停",
        ],
        "url": "https://waifly.com/guides/free-nodejs-hosting",
        "source": "Waifly 官方免费 Node.js 托管说明（2026-08-12 更新，创始人撰写：300MB / 1GB / MySQL、永久免费、离线 3 天暂停、一人一账号）+ Waifly 官网中文页与 docs.waifly.com",
        "risk": "没有 root 与 SSH，装不了系统包；300MB 内存是硬上限，构建型任务与 Puppeteer 跑不了；离线 3 天会被暂停，需要保持进程活跃；一人一账号，多开会被自动检查处理；只有巴黎节点，亚洲访问延迟偏高。",
        "added_at": "2026-11-21T16:22:10+08:00",
        "verified": True,
        "last_verified": "2026-11-21",
        "added": "2026-11-21",
        "status": "active",
    },
    {
        "id": "wispbyte-free-24-7-panel",
        "title": "[全球] Wispbyte 免费 24/7 面板机：512MB 内存 + 1GB 硬盘，免绑卡、登录保活",
        "brand": "Wispbyte",
        "domain": "wispbyte.com",
        "category": "cloud",
        "value": "512MB 内存 + 1GB 硬盘，永久免费（付费 €4.99/年起）",
        "value_num": 0,
        "cost": "真正免费",
        "highlight": "官网写「Free hosting forever，no renewals, no credits needed」：512MB 内存、1GB 硬盘、一台常驻不休眠的服务器，免信用卡；每 14 天登录面板一次保活即可，2026-10-31 起统一迁到自家客户端面板",
        "regions": "[全球] 网上面板注册（wispbyte.com/client），支持 Discord 账号快速登录；免信用卡，每账号一台免费服务器",
        "start": "",
        "end": "",
        "content": "Wispbyte 是做免费 24/7 托管的平台，官网首页直接写「Free hosting forever! No renewals, no credits needed」，适合跑 Discord 机器人、Telegram 机器人、小型 Node / Python 服务与静态站。\n\n免费档规格：512MB 内存 + 1GB 硬盘、每个账号一台、常驻不休眠、崩溃自动重启，注册不需要信用卡也不用付款。保活规则是每 14 天登录一次面板，官方口径是没有续费按钮、不用看广告赚积分。付费从 €4.99/年起，主要买更多内存与实例数。\n\n重要变更（官方 2026-10-31 公告）：平台已从 Pterodactyl（free.wispbyte.com 与 pro.wispbyte.com）迁到自家客户端面板，所有服务器都在 Wispbyte client panel 里管理，旧面板对客户关闭。所以现在建服、传文件、看日志都在同一个网页控制台完成，不再有翼龙面板那套 egg 选择。\n\n注册与开机流程：wispbyte.com/client 注册（可用 Discord 授权，最快）→ 在 Dashboard 点 Create Server，填名称与描述 → 上传代码或连 Git 仓库 → 设置启动命令与环境变量 → Start。启动前有时会弹一次奖励广告，这是免费档的成本来源。\n\n适合什么：一个常驻的小型机器人、轻量 API、Webhook 接收端、定时任务。512MB 是硬上限，大型应用、多实例、重数据库都跑不动，也别把它当正式生产环境。",
        "conditions": "免费档：512MB 内存 / 1GB 硬盘 / 每账号一台、常驻不休眠，免信用卡、无续费按钮与积分要求；每 14 天登录面板一次保活；启动前可能出现奖励广告；2026-10-31 起只在 Wispbyte client panel 管理，旧翼龙面板已关闭；禁止滥用。",
        "steps": [
            "打开 wispbyte.com/client 注册（可用 Discord 账号快速注册，不需要付款）",
            "在 Dashboard 点 Create Server，填服务器名称与描述",
            "上传代码或连接 Git 仓库，设置启动命令与环境变量",
            "点 Start 运行；每 14 天登录一次面板保活",
        ],
        "url": "https://wispbyte.com/",
        "source": "Wispbyte 官方首页（Free hosting forever / 免信用卡）与官方博客「Moving Away from Pterodactyl」（2026-10-31，迁移到 client panel）+ Space-Node 免费机器人主机横评（2026-11-03 记录：512MB / 1GB、每 14 天登录、无需广告与积分）",
        "risk": "512MB 内存是硬上限，重应用会 OOM；每 14 天不登录有被回收的风险；启动前的奖励广告会拖慢开机；2026-10 起面板迁移，旧教程与旧控制台入口都已失效；节点规模有限，延迟与稳定性不如付费主机，别当生产环境。",
        "added_at": "2026-11-21T16:24:00+08:00",
        "verified": True,
        "last_verified": "2026-11-21",
        "added": "2026-11-21",
        "status": "active",
    },
]

EN_NEW = {
    "waifly-free-nodejs-panel": {
        "title": "[Global] Waifly permanent free Node.js panel host: 300MB RAM, 1GB storage and one MySQL database",
        "brand_en": "Waifly",
        "highlight": "A Pterodactyl panel host in Paris with a permanent free tier at zero cost, no card and no time limit: 300MB RAM, 30% of a vCPU, 1GB storage, one MySQL database and one port, plus a live console, web file manager, SFTP, scheduled tasks and backups; a server offline for three days is suspended",
        "regions": "[Global] Registered on the web panel at dash.waifly.com with nodes in Paris FR1 and FR2; the free tier needs no credit card and allows one account per person",
        "value": "300MB + 1GB + MySQL",
        "content": "Waifly is a French team's free Node.js host, and the official page is explicit: the free tier is permanently zero cost rather than a trial, with no expiry date, no credit card and no monthly hour quota, so the process keeps running.\n\nThe allocation: 300MB RAM, 30% of a single core, 1GB storage, one MySQL database and one port, running as a container under Pterodactyl on Proxmox and Docker. There is no root and no SSH, but you get a live console, a web file manager with an editor, SFTP, scheduled tasks, backups and DDoS protection on every plan.\n\nHow to start: sign up at dash.waifly.com, open Servers and create one, choosing the NodeJS Egg and the Paris FR1 or FR2 location; upload your project with package.json and dependencies install on start. On the Startup tab point the entry at your main file (node index.js or npm start) and read the port from the environment variable rather than hard-coding it. To use your own domain, point its A record at the server IP and declare the domain in domain management, where an Nginx reverse proxy is generated.\n\nWhat fits: Discord bots, Express or Fastify REST APIs, Telegram bots, scheduled scrapers, webhook receivers and static sites behind Nginx all live inside 300MB, since Node itself takes about 40 to 50MB. What does not fit: building Next.js on the server, Puppeteer or headless Chrome, and audio or video transcoding, which start at the 4 euro Nano plan.\n\nRisk rules: the anti-abuse policy suspends a server that stays offline for more than three days, and one account per person is enforced with an automated check every 30 minutes, so duplicate accounts get handled.",
        "conditions": "Free tier: 300MB RAM, 30% of a vCPU, 1GB storage, one MySQL database and one port, permanently zero cost with no card and no time limit; a server offline for more than three days is suspended automatically; one account per person with no duplicates; no root or SSH, with management through the panel, SFTP and MySQL only.",
        "steps": [
            "Register at dash.waifly.com, since the free tier needs no credit card",
            "Open Servers, click Create, choose the NodeJS Egg and the FR1 or FR2 location, and the free limits apply automatically",
            "Upload the project with its package.json and set the entry file and start command on the Startup tab",
            "Start it and read the npm install output and logs in the live console; keep the server online, since three days offline suspends it",
        ],
        "risk": "No root and no SSH means no system packages; 300MB is a hard ceiling, so builds and Puppeteer do not run; three days offline suspends the server, so the process must stay active; one account per person is enforced by automated checks; only Paris nodes are available, so latency from Asia is high.",
        "source": "Waifly official free Node.js hosting guide (updated 12 August 2026, written by the founder: 300MB, 1GB, MySQL, permanently free, three-day offline suspension, one account per person) + Waifly official site and docs.waifly.com",
    },
    "wispbyte-free-24-7-panel": {
        "title": "[Global] Wispbyte free 24/7 panel host: 512MB RAM and 1GB of disk with no card, kept alive by logging in",
        "brand_en": "Wispbyte",
        "highlight": "The official site says free hosting forever with no renewals and no credits needed: 512MB RAM, 1GB of disk and one always-on server with no credit card; logging into the panel once every 14 days keeps it, and since 31 October 2026 everything runs in Wispbyte's own client panel",
        "regions": "[Global] Registered on the web panel at wispbyte.com/client, with Discord sign-in available; no credit card and one free server per account",
        "value": "512MB RAM + 1GB disk",
        "content": "Wispbyte is a free 24/7 hosting platform whose homepage states free hosting forever with no renewals and no credits needed. It suits Discord and Telegram bots, small Node or Python services and static sites.\n\nThe free tier: 512MB RAM, 1GB of disk, one server per account, always on with no sleep and automatic restarts, and no credit card or payment at sign-up. The keep-alive rule is one panel login every 14 days, and officially there is no renew button and no ad or coin grinding. Paid plans start at 4.99 euros a year for more memory and instances.\n\nImportant change, from the official 31 October 2026 announcement: the platform moved off Pterodactyl, where free.wispbyte.com and pro.wispbyte.com are now disabled for customers, and every server is managed in the Wispbyte client panel. Creating servers, uploading files and reading logs all happen in that one web console, without the old egg selector.\n\nSign-up and start-up: register at wispbyte.com/client, where Discord authorisation is fastest, then click Create Server in the dashboard, give it a name and description, upload code or connect a Git repository, set the start command and environment variables, and press Start. A reward ad may appear before Start, which is how the free tier is funded.\n\nWhat fits: one always-on small bot, a light API, a webhook receiver or a scheduled job. The 512MB ceiling is hard, so large applications, multiple instances and heavy databases do not run here, and it is not a production environment.",
        "conditions": "Free tier: 512MB RAM, 1GB disk, one server per account, always on with no sleep, no credit card and no renew button or credits; one panel login every 14 days keeps it alive; a reward ad may appear before Start; since 31 October 2026 management is only in the Wispbyte client panel, with the old Pterodactyl panel closed; abuse is prohibited.",
        "steps": [
            "Register at wispbyte.com/client, where a Discord account is the fastest route and no payment is needed",
            "In the dashboard click Create Server and fill in the server name and description",
            "Upload code or connect a Git repository, then set the start command and environment variables",
            "Press Start to run it, and log into the panel once every 14 days to keep it",
        ],
        "risk": "512MB is a hard ceiling and heavier applications run out of memory; missing the 14-day login risks reclamation; the reward ad before Start slows boot; the October 2026 panel migration makes older tutorials and old console links obsolete; nodes are limited, so latency and stability trail paid hosts and it should not be treated as production.",
        "source": "Wispbyte official homepage (free hosting forever, no card) and official blog post Moving Away from Pterodactyl (31 October 2026, migration to the client panel) + Space-Node free bot hosting comparison (3 November 2026: 512MB / 1GB, 14-day login, no ads or credits required)",
    },
}


def main() -> None:
    deals = json.loads(DP.read_text(encoding="utf-8"))
    ens = json.loads(EP.read_text(encoding="utf-8"))
    for d in deals:
        if d["id"] in ZH:
            d.update(ZH[d["id"]])
        if d["id"] in EN:
            ens[d["id"]].update(EN[d["id"]])
    have = {d["id"] for d in deals}
    for d in NEW:
        if d["id"] in have:
            continue
        deals.append(d)
        ens[d["id"]] = EN_NEW[d["id"]]
    DP.write_text(json.dumps(deals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EP.write_text(json.dumps(ens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("total", len(deals))


if __name__ == "__main__":
    main()
