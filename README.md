# 大学生生涯规划智能小助手

> **这是上海交通大学的部署分支（`sjtu-production`），不是产品主线。**
> 学生上游仓库：[labixiaoji/SIYUAN-COMPASS](https://github.com/labixiaoji/SIYUAN-COMPASS)。
> 本分支只在上游之上增加校内适配：jAccount 单点登录、校内 DeepSeek 网关、`/shengya/`
> 子路径部署、systemd/Nginx 模板，以及关闭生产环境的本地注册与密码登录。
> 业务功能一律以上游为准，本分支不改问卷、Prompt 和报告逻辑。
>
> 部署结构、认证来源、更新与回退步骤见 [`docs/部署记录-2026-07-24.md`](docs/部署记录-2026-07-24.md)。
> 上游 README 中「登录方式仅用于本地开发」「真实 jAccount 由学校侧负责」指的正是本分支已经做完的部分。

一个面向学生的生涯规划问卷与 AI 报告系统，采用 React、FastAPI、PostgreSQL 和 Docker Compose。

## 文档

- [01-问卷与报告规范](docs/01-问卷与报告规范.md)
- [02-系统实现文档](docs/02-系统实现文档.md)
- [03-部署与运维文档](docs/03-部署与运维文档.md)
- [04-数据隐私与保留策略](docs/04-数据隐私与保留策略.md)
- [05-开发与测试文档](docs/05-开发与测试文档.md)
- [06-版本更新记录](docs/06-版本更新记录.md)

## 快速开始

项目统一使用根目录的 .env 文件。首次运行：

~~~bash
cp .env.example .env
~~~

至少填写当前模型通道的 API Key、AUTH_SECRET、ADMIN_PASSWORD 和 POSTGRES_PASSWORD。

本地 Docker 开发：

~~~bash
docker compose -f docker-compose.dev.yml up -d --build
~~~

本地访问前端 http://localhost:5173，后端 http://localhost:8000。

服务器生产部署：

~~~bash
docker compose up -d --build
~~~

生产配置、更新、日志和故障排查见部署与运维文档。

## 当前范围

- 学生可填写七步问卷、保存云端草稿、生成报告、查看历史报告和提交反馈。
- 报告生成使用可恢复的 PostgreSQL 持久任务，默认不限制每日生成次数，可通过环境变量设置配额。
- 管理员可查看学生记录、查看完整问卷、编辑报告并查询审计记录。
- 语音转写接口已接入，默认关闭，启用前需要完成供应商配置和学校侧隐私审核。
- 当前登录方式仅用于本地开发和联调，真实 jAccount 接入由学校侧负责。

## 检查命令

~~~bash
cd backend
python -m unittest discover -s tests
~~~

~~~bash
cd frontend
npm test
npm run typecheck
npm run build
~~~
