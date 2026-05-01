# LinkedIn 求职助手

一个基于 Chrome 扩展、FastAPI 和 Playwright 的本地 LinkedIn 求职辅助工具，用于职位筛选、简历管理、Easy Apply 辅助投递和申请记录追踪。

## 项目简介

这个项目的目标不是“全自动海投”，而是构建一个更安全、可控、可追踪的本地求职工作流。系统由两个部分组成：

- `chrome-extension/`
  - 提供弹窗控制面板
  - 提供筛选器和简历管理页面
  - 提供投递记录仪表盘
  - 负责与本地后端通信
- `backend/`
  - 基于 FastAPI 提供本地 API
  - 使用 SQLite 管理职位、简历、筛选条件和投递记录
  - 使用 Playwright 执行浏览器自动化
  - 提供速率限制、人工登录、日志记录等安全机制

## 核心能力

- LinkedIn 职位筛选与管理
- 多份简历上传与本地管理
- Easy Apply 流程自动化辅助（含 dry-run "模拟提交"模式）
- 投递记录追踪与状态查看
- 本地 SQLite 数据存储（启用 WAL，并发更稳）
- 基于规则的速率限制与安全控制
- 保留浏览器登录态，减少重复登录成本
- 投递后可选自动连接 recruiter / hiring manager（个人化文案模板，可热更新）

## 项目特点

- 本地优先：数据默认保存在本机，不依赖云端服务
- 可控性强：由用户决定何时启动、何时停止、使用哪个筛选器
- 可追踪：每次投递、失败、跳过都有记录
- 可扩展：后端 API、自动化模块、扩展前端结构清晰，适合继续迭代

## 当前仓库包含什么

目前仓库已经包含：

- Chrome 扩展前端代码
- FastAPI 后端服务
- SQLite 模型与基础 API
- Playwright 自动化模块
- 配置文件与测试代码
- 本地运行所需的主要文档

需要注意：

- 仓库不会提交你的本地数据库、浏览器登录态、简历文件、日志和敏感配置
- 新环境克隆后，需要重新配置 `.env`、扩展 ID 和本地运行数据

## 适用场景

- 想系统化管理 LinkedIn 投递流程
- 想在本地维护职位、筛选条件和简历版本
- 想在人工可控的前提下，提高 Easy Apply 的执行效率
- 想把求职过程沉淀成可复用工具，而不是一次性脚本

## 首次启动提示

如果你是第一次克隆仓库，建议优先阅读：

- [README.md](./README.md) - 英文主说明，包含当前推荐启动流程
- [QUICKSTART.md](./QUICKSTART.md) - 最短启动路径
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - 测试与验证说明
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 系统结构说明

首次运行时，请特别注意这几项：

- 需要在 `backend/.env` 中配置 `LJA_EXTENSION_ID`
- 启动后端时建议使用 `--env-file .env`
- 需要手动加载 Chrome unpacked extension
- 需要自行创建筛选器、上传简历
- 拷贝 `backend/data/config/form_answers.yaml.example` → `form_answers.yaml`，再填入真实信息（这个文件已被 gitignore，不会提交）

## ⚠️ 隐私 / PII 注意事项

以下文件**含个人敏感数据**，已加入 `.gitignore`，请永远不要 `git add`：

- `backend/data/config/form_answers.yaml` — 真实姓名 / 电话 / 邮箱 / 工作授权 / GPA / 期望薪资
- `backend/data/config/connection_messages.yaml` — 自定义 recruiter 邀请文案
- `backend/data/config/api_key.txt` — 后端访问凭证
- `backend/data/config/runtime_settings.json` — 通过 UI 修改的限速等运行时配置
- `backend/data/chrome_profile/` — CDP 模式下自动创建的 Chrome 用户目录，**包含 LinkedIn 登录 Cookie**
- `backend/data/browser_profile/`、`backend/data/db/`、`backend/data/logs/`、`backend/data/resumes/`

提交前务必跑一次 `git status`，确认这些路径都不在暂存区。

## 数据库迁移

ORM 第一次启动会自动 `init_db()` 建表。如果在已有 DB 上添加了索引（例如本次的 connections 表），跑一次幂等迁移：

```bash
cd backend
source venv/bin/activate
python -m scripts.migrate_indexes
```

## 安全设计

- 后端只绑定 `127.0.0.1`，不对外暴露
- 所有 `/api/*` 路由强制 `X-API-Key`，使用 `secrets.compare_digest` 常量时间比较
- CORS 在配了 `LJA_EXTENSION_ID` 时只放行该扩展 ID + localhost；否则使用正则匹配 + `allow_credentials=False`，避免"通配 + credentials"的浏览器禁止组合
- `/settings POST` 只接受白名单字段（限速、延迟、networking 三类），写入 `runtime_settings.json` 后重启仍然生效
- 速率限制 + 预热曲线（warmup）+ 模拟人类延迟，降低被风控的概率

## 安全说明

这个项目会辅助执行 LinkedIn 上的求职操作。请保守使用、人工复核提交内容，并假设 LinkedIn 的页面结构、选择器和风控策略会随时变化。
