# 大学生生涯规划智能小助手

学生原始项目：[labixiaoji/SIYUAN-COMPASS](https://github.com/labixiaoji/SIYUAN-COMPASS)。本目录在原项目基础上增加了上海交通大学校内 DeepSeek、jAccount 单点登录和 `/shengya/` 子路径部署支持。

正式环境的部署结构、认证来源、更新和回退步骤见 [`docs/部署记录-2026-07-24.md`](docs/部署记录-2026-07-24.md)。

大学生生涯规划智能小助手采用前后端分离结构：

```text
frontend/  React + TypeScript + Vite
backend/   Python + FastAPI
postgres  PostgreSQL 数据库
```

生产环境使用 PostgreSQL 保存数据，并按业务对象拆分表：

```text
users                  用户账号
assessment_responses   问卷单值答案
assessment_scores      能力与兴趣量表分数
assessment_choices     问卷多选答案
career_profiles        结构化人生画像
reports                当前报告
report_versions        报告历史版本
generation_jobs        生成任务
report_feedback        报告反馈
admin_audit_logs        管理员操作记录
```

各表通过 UUID 关联，不使用用户名建立关系。画像和报告正文等复杂结构使用
`JSONB` 保存，核心关联字段单独建列，方便后续查询和迁移。

系统包含学生账号和管理员账号：

- 学生通过 jAccount 登录后填写问卷，报告自动归入当前账号，并可在“我的报告”中查看历史记录；本地开发可选择开启测试账号。
- 管理员可查看全部学生生成记录、打开报告，并人工修改报告标题和正文。
- 学生只能访问自己的生成任务、报告和反馈页面。

报告生成采用两阶段大模型流程：

```text
问卷回答
  -> 依据每道题的解释规则生成结构化用户画像
  -> 校验证据、反证、矛盾、信息缺口和 Plan A / Plan B
  -> 基于原始回答和结构化画像生成六模块报告
```

画像只做宽松的可用性校验：只要包含可用于报告生成的核心分析内容就会继续，缺失的辅助字段会记录为质量警告。画像生成成功后会立即保存问卷、结构化画像、模型原始输出和质量警告；后续报告生成失败不会丢失画像。

前端使用生成任务接口展示实时阶段：

```text
POST /api/assessment-jobs
GET  /api/assessment-jobs/{jobId}
```

原有 `POST /api/assessments` 同步接口仍然保留，适合通过 ApiPost 直接测试。

## 本地启动

首次运行先在项目根目录创建唯一环境配置：

```bash
cp .env.example .env
```

本地默认使用 DeepSeek，至少填写模型通道的 API Key：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY
AUTH_SECRET
ADMIN_PASSWORD
POSTGRES_PASSWORD
```

校内服务器也可以直接复用 `/etc/course-ai.env` 中的 `AI_API_KEY`、`AI_API_BASE` 和 `AI_MODEL`。Kimi 通道仅作为兼容选项保留。

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问地址：

```text
前端：http://localhost:5173
后端：http://localhost:8000
接口文档：http://localhost:8000/docs
```

## 环境变量

项目只保留根目录 `.env` 作为唯一环境配置文件。本地后端、本地前端和 Docker Compose 都读取这一份配置：

```text
LLM_PROVIDER=deepseek
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://models.sjtu.edu.cn/api/v1
DEEPSEEK_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=180
FRONTEND_ORIGINS=http://localhost:5173,http://localhost:8080,http://localhost
VITE_API_BASE_URL=http://localhost:8000/api
VITE_BASE_PATH=/
VITE_ENABLE_LOCAL_AUTH=true
AUTH_SECRET=please-change-to-a-long-random-string
AUTH_TOKEN_HOURS=72
LOCAL_AUTH_ENABLED=true
PORTAL_SESSION_SECRET=
PORTAL_SESSION_COOKIE_NAME=session
PORTAL_LOGIN_URL=https://ai4edu.sjtu.edu.cn/auth/jaccount/login
PORTAL_LOGOUT_URL=https://ai4edu.sjtu.edu.cn/auth/logout
PUBLIC_APP_URL=http://localhost:5173
APP_BASE_PATH=/
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin12345
ADMIN_DISPLAY_NAME=系统管理员
POSTGRES_DB=siyuan_compass
POSTGRES_USER=siyuan
POSTGRES_PASSWORD=please-change-postgres-password
DATABASE_URL=postgresql://siyuan:please-change-postgres-password@localhost:5432/siyuan_compass
HTTP_PORT=8080
```

`LLM_PROVIDER` 支持 `kimi` 和 `deepseek`，只会调用当前选中的通道。必须配置该通道对应的 API Key。模型未配置、超时或调用失败时，报告接口会直接返回错误，不会生成备用模板报告。

首次启动时，后端会根据 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 创建管理员账号。部署或提供给真实学生使用前，必须修改默认管理员密码和 `AUTH_SECRET`。

生产环境设置 `LOCAL_AUTH_ENABLED=false` 和 `VITE_ENABLE_LOCAL_AUTH=false` 后，注册、密码登录和本地管理员入口均关闭，用户统一通过 jAccount 登录。系统复用同域门户的签名 session cookie，不保存 jAccount 密码或 OAuth access token。

## 交大服务器部署

当前正式访问地址为：<https://ai4edu.sjtu.edu.cn/shengya/>。

部署结构如下：

```text
浏览器 /shengya/      -> Nginx 静态前端（127.0.0.1:18121）
浏览器 /shengya/api/  -> FastAPI（127.0.0.1:18120）
FastAPI               -> PostgreSQL 16 + 校内 DeepSeek
jAccount              -> 同域 portal OAuth -> 签名 session -> 本系统本地用户映射
```

部署文件位于 `deploy/`：

- `siyuan-compass.service`：FastAPI systemd 服务。
- `siyuan-compass.env.example`：生产环境变量模板，不含密钥。
- `nginx-siyuan-compass-static.conf`：内部静态站点。
- `nginx-siyuan-compass-public.conf`：加入 `ai4edu` 主站的 `/shengya/` 路由。

前端生产构建命令：

```bash
cd frontend
VITE_BASE_PATH=/shengya/ \
VITE_API_BASE_URL=/shengya/api \
VITE_ENABLE_LOCAL_AUTH=false \
npm run build
```

服务器的 `/etc/siyuan-compass.env` 必须由管理员在服务器上创建并设为 `0600`，其中 `PORTAL_SESSION_SECRET` 取自门户现有 `PORTAL_SECRET_KEY`；该值不得提交到代码仓库。后端同时读取 `/etc/course-ai.env`，直接使用学校的 `AI_API_KEY`，模型固定为 `deepseek-chat`。

登录相关页面：

```text
学生登录：http://localhost:5173/login
学生注册：http://localhost:5173/register
管理员后台：http://localhost:5173/admin
```

## Docker 配置

项目明确区分两套 Compose：

- `docker-compose.yml`：服务器生产部署。
- `docker-compose.dev.yml`：本地开发和热更新。

### 服务器生产部署

生产版使用 Nginx 托管前端，后端不直接暴露到公网，数据保存在 `postgres-data` volume。

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

更新服务器代码：

```bash
git pull
docker compose up -d --build
```

修改服务器 `.env` 后：

```bash
docker compose up -d --force-recreate backend
```

### 本地开发

本地必须显式指定开发文件：

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

本地访问地址：

```text
前端：http://localhost:5173
后端：http://localhost:8000
```

开发版特点：

- 使用项目名 `siyuan-compass-dev` 和数据库 volume `postgres-dev-data`。
- 后端挂载 `backend/app`，并使用 `uvicorn --reload`。
- 前端挂载 `frontend`，并运行 Vite dev server。
- 前端依赖安装在 Docker volume `frontend-node-modules`，不会覆盖宿主机的 `frontend/node_modules`。

停止开发模式：

```bash
docker compose -f docker-compose.dev.yml down
```

本地更新代码后通常会热更新；修改 `.env` 后需要执行：

```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate backend
```
