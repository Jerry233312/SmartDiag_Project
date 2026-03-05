# 智诊 SmartDiag — 乡村医生 AI 辅助问诊实训平台0.10.0

> 基于腾讯云大模型知识引擎（LKE）的游戏化医学实训系统。学员扮演乡村医生，在金币预算约束下向 AI 患者问诊、使用医疗器械检查，并提交最终诊断，由 AI 主任考官实时评分。

---

## 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [环境变量配置](#环境变量配置)
- [核心业务逻辑](#核心业务逻辑)
- [API 接口文档](#api-接口文档)
- [病例数据管理](#病例数据管理)
- [项目架构说明](#项目架构说明)

---

## 项目简介

**SmartDiag（智诊）** 是一个面向基层医疗培训的 AI 辅助问诊实训平台，核心特性包括：

- **五阶关卡体系**：A（助理医师）→ E（主任医师），难度递进，初始金币预算逐级降低
- **AI 患者角色扮演**：通过腾讯云 LKE RAG 技术，将结构化病例元数据注入大模型，让 AI 沉浸式扮演具体患者
- **医疗经济学约束**：每项器械检查消耗金币，考核学员在有限资源下的诊断决策能力
- **AI 实时评分**：问诊结束后由 AI 主任考官依据标准答案打分，并专项评价检查费用合理性
- **30 条内置病例**：涵盖糖尿病、高血压两大慢病领域，支持从 Word 题库扩充

---

## 技术栈

### 后端

| 技术 | 版本 | 说明 |
|---|---|---|
| Python | 3.11 | 运行时环境 |
| FastAPI | ≥ 0.110.0 | 异步 Web 框架 |
| Uvicorn | ≥ 0.27.0 | ASGI 服务器 |
| SQLAlchemy | ≥ 2.0.0 | ORM，StaticPool 模式 |
| SQLite | 本地文件 | 开发数据库（`smartdiag.db`） |
| Pydantic | ≥ 2.5.0 | 数据校验与序列化 |
| httpx + httpx-sse | ≥ 0.26.0 | 异步 HTTP 客户端 + SSE 解析 |
| python-dotenv | ≥ 1.0.0 | 环境变量加载 |
| pandas + python-docx | — | Word 题库解析脚本依赖 |

### 前端

| 技术 | 版本 | 说明 |
|---|---|---|
| Vue 3 | ^3.5.25 | 渐进式前端框架（Composition API） |
| TypeScript | ~5.9.3 | 类型安全 |
| Vite | ^5.4.11 | 构建工具 |
| Vue Router | ^4.6.4 | 客户端路由 |
| Pinia | ^3.0.4 | 全局状态管理 |
| Tailwind CSS v4 | ^4.2.1 | 原子化 CSS 样式 |
| Axios | ^1.13.5 | HTTP 请求封装 |

### 外部服务

| 服务 | 用途 |
|---|---|
| 腾讯云 LKE 大模型知识引擎 | AI 患者扮演 + RAG 知识库检索 + 诊断评分 |
| 腾讯云 API 密钥（TC3 鉴权） | `SECRET_ID` / `SECRET_KEY` 生成签名 Header |

---

## 目录结构

```
SmartDiag_Project/
├── backend/
│   ├── main.py              # FastAPI 主入口，含全部路由与核心业务逻辑
│   ├── models.py            # SQLAlchemy ORM 模型（5 张表）
│   ├── database.py          # SQLite 连接 + SessionLocal + DeclarativeBase
│   ├── data_parser.py       # Word 题库 → cases.csv 解析脚本
│   ├── cases.csv            # 结构化病例数据（由 data_parser.py 生成）
│   ├── requirements.txt     # Python 依赖清单
│   ├── .env.example         # 环境变量模板（⚠️ 真实 .env 已 gitignore）
│   └── services/
│       └── ai_client.py     # 腾讯云 LKE 客户端（TC3 鉴权 + SSE 流式 + 评分解析）
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── LevelSelect.vue    # 关卡选择页（五阶入口）
│   │   │   └── Workspace.vue      # 问诊主工作台（核心交互页面）
│   │   ├── store/
│   │   │   └── consultation.ts    # Pinia Store（预算 / 对话 / 器械记录）
│   │   ├── api/
│   │   │   └── request.ts         # Axios 封装 + SSE 消费逻辑
│   │   └── router/
│   │       └── index.ts           # 路由配置
│   ├── package.json
│   └── vite.config.ts
├── start_game.bat           # Windows 一键启动脚本
├── 启动.txt                 # 手动启动说明
└── .gitignore               # 排除 .env / .venv / node_modules / *.db
```

---

## 环境要求

- **Python** 3.10+
- **Node.js** 18+（含 npm）
- **腾讯云 LKE** 已开通的 Bot 应用（获取 BOT_APP_KEY）
- **腾讯云 API 密钥**（获取 SECRET_ID / SECRET_KEY）

---

## 快速启动

### 1. 克隆仓库

```bash
git clone https://github.com/Jerry233312/SmartDiag_Project.git
cd SmartDiag_Project
```

### 2. 配置后端环境变量

```bash
cd backend
cp .env.example .env
# 用编辑器打开 .env，填入真实密钥
```

### 3. 安装后端依赖并启动

```bash
# 在 backend/ 目录下
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 28080
```

后端启动后，数据库表会自动创建，30 条演示病例数据自动播种。

访问 API 文档：http://localhost:28080/docs

### 4. 安装前端依赖并启动

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

前端默认运行于：http://localhost:5173

---

## 环境变量配置

在 `backend/.env` 中配置以下变量（参考 `.env.example`）：

```env
# 腾讯 LKE 知识引擎 Bot 密钥
BOT_APP_KEY=your_bot_app_key_here

# 腾讯云 API 密钥
SECRET_ID=your_secret_id_here
SECRET_KEY=your_secret_key_here

# LKE SSE 接口地址（一般无需修改）
LKE_SSE_URL=https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse
```

> **安全说明**：`.env` 已被 `.gitignore` 永久排除，绝不会提交到版本库。

---

## 核心业务逻辑

### 五阶关卡体系

病例 ID 首字母对应关卡等级，初始金币预算随等级降低：

| 等级 | 职称 | 初始金币 | 病例前缀 |
|---|---|---|---|
| 1 | 助理医师 | 1000 | A |
| 2 | 住院医师 | 800 | B |
| 3 | 主治医师 | 500 | C |
| 4 | 副主任医师 | 500 | D |
| 5 | 主任医师 | 500 | E |

### 器械检查金币消耗

| 检查项目 | 金币消耗 |
|---|---|
| 体温测量 | 10 |
| 血氧检测 / 血压测量 | 20 |
| 视诊 | 30 |
| 听诊 / 叩诊 / 触诊 | 50 |
| 心电图 / 血常规 | 100 |
| 尿常规 | 80 |
| 血糖检测 | 120 |
| 生化检查 | 150 |
| 超声检查 / X 光检查 | 200 |
| CT 检查 | 500 |
| 核磁共振 | 800 |

### AI 评分规则（满分 100 分）

- 少做一项必要检查：**-10 分/项**
- 多做无指征的过度检查：**-5 分/项**
- 最终诊断严重错误：**总分上限 49 分**
- 门诊记录完全空白：**-10 分**
- 金币使用率极低且诊断正确：**+5~10 分**（表彰医疗经济学素养）
- 过度医疗（花费 > 40% 预算但诊断简单）：**额外扣 5~15 分**

### AI 技术架构（RAG 驱动）

```
学员输入问诊内容
      ↓
FastAPI 后端提取病例 kb_query（知识库检索词）
      ↓
构建「患者角色人设」Prompt 注入 LKE
      ↓
LKE 在腾讯知识库中检索对应病历档案
      ↓
AI 以该患者身份流式回答（SSE 实时推送）
      ↓
问诊结束 → 聚合记录 → AI 考官评分（再次调用 LKE）
```

---

## API 接口文档

后端运行后访问 **http://localhost:28080/docs** 查看 Swagger 自动文档。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/cases` | 获取病例列表，支持 `level` 过滤与 `random_pick` 随机抽取 |
| `POST` | `/api/consultation/start` | 开始新问诊，初始化预算，返回 `record_id` |
| `POST` | `/api/consultation/chat` | 发送问诊消息，SSE 流式返回 AI 患者回复 |
| `POST` | `/api/consultation/instrument` | 使用诊察器械，扣除金币，返回检查结果 |
| `POST` | `/api/consultation/submit` | 提交最终诊断，触发 AI 评分，返回得分与评语 |
| `GET` | `/health` | 服务健康检查 |

### SSE 数据格式

`/api/consultation/chat` 返回的 SSE 流格式：

```
data: {"content": "文字片段"}\n\n
...
data: [DONE]\n\n
```

---

## 病例数据管理

### 数据源优先级

启动时自动按以下优先级播种病例：

```
cases.csv（由 data_parser.py 解析 Word 题库生成）
    ↓ 不存在时降级
MOCK_CASES（main.py 内置 30 条演示病例，含 A1-A10 / B1-B10 / C1-C10）
```

### 从 Word 题库扩充病例

```bash
cd backend
python data_parser.py   # 解析 Word 题库，生成/更新 cases.csv
# 重启后端后自动重新播种
```

### 数据库表结构

| 表名 | 说明 |
|---|---|
| `users` | 学员账户（username / password_hash / total_score） |
| `cases` | 病例元数据（title / tencent_kb_id / standard_answer JSON / initial_budget） |
| `consultation_records` | 问诊会话（status / budget_left / final_score / ai_evaluation） |
| `dialogue_messages` | 医患对话记录（role: user/assistant） |
| `instrument_logs` | 器械检查日志（action_name / result_text / cost） |

---

## 项目架构说明

```
前端（Vue 3 SPA）          后端（FastAPI）          外部服务
localhost:5173      →     localhost:28080    →    腾讯云 LKE
                                ↓
                          SQLite（本地）
                          smartdiag.db
```

- 所有业务逻辑（预算管理 / 状态校验 / AI 交互）收敛在后端
- 前端仅负责渲染和请求发送，不持有任何业务状态
- SSE 流式响应通过 FastAPI `StreamingResponse` + 异步生成器实现
- 后端启动时自动建表（`Base.metadata.create_all`）并播种演示数据，无需手动初始化数据库

---

## License

本项目为内部实训平台，仅供教育用途。
