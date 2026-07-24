# app-scanner 使用指南

## 快速开始

### 1. 扫描所有应用（默认同时生成到所有平台）

```
/scan-apps
```

这将：
1. 扫描当前工作区
2. 查找所有后端和前端应用（无需预先配置 openspec）
3. 分析每个应用的代码结构
4. **同时生成技能文件到三个平台**：
   - `.claude/skills/*/SKILL.md`
   - `.cursor/skills/*/SKILL.md`
   - `.codex/skills/*/SKILL.md`

### 2. 仅生成到指定平台

```
/scan-apps --target claude     # 仅生成到 .claude/skills/
/scan-apps --target cursor     # 仅生成到 .cursor/skills/
/scan-apps --target codex      # 仅生成到 .codex/skills/
/scan-apps --target claude --target cursor  # 生成到多个指定平台
```

### 3. 指定工作区

```
/scan-apps /workspace/IdeaProjects/retail
```

### 4. 增量扫描（只扫描有变化的应用）

```
/scan-apps --incremental
```

## 多平台支持

生成的 SKILL.md 文件格式兼容以下 AI 编程工具：

| 工具 | 目录 | 默认行为 |
|------|------|----------|
| Claude Code | `.claude/skills/` | ✅ 默认生成 |
| Cursor | `.cursor/skills/` | ✅ 默认生成 |
| Codex | `.codex/skills/` | ✅ 默认生成 |

**默认**：扫描完成后，技能文件会同时复制到所有三个平台目录。

## 支持的应用类型

### 后端应用

| 语言/框架 | 识别文件 |
|-----------|----------|
| Java (Maven) | `pom.xml` |
| Java (Gradle) | `build.gradle`, `build.gradle.kts` |
| Go | `go.mod` |
| Node.js (后端) | `package.json` + express/koa/nest |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py` |

### 前端应用

| 框架 | 识别依据 |
|------|----------|
| React | `package.json` 包含 react/react-dom |
| Vue | `package.json` 包含 vue/vue-router |
| Angular | `package.json` 包含 @angular/core |
| Next.js | `package.json` 包含 next |
| Nuxt.js | `package.json` 包含 nuxt |
| Remix | `package.json` 包含 remix 或 @remix-run |
| Svelte | `package.json` 包含 svelte |
| Solid.js | `package.json` 包含 solid-js |

**额外识别**：
- 前端配置文件：`vite.config.js`, `vue.config.js`, `angular.json`, `next.config.js`, `webpack.config.js`, `tailwind.config.js`
- 典型目录结构：`src/pages/`, `src/components/`, `public/`

## 输出文件结构

扫描完成后，将生成以下文件：

```
.claude/
└── skills/
    ├── cart-service/      # 后端应用
    │   └── SKILL.md
    ├── order-service/     # 后端应用
    │   └── SKILL.md
    ├── admin-frontend/         # 前端应用
    │   └── SKILL.md
    └── customer-web/           # 前端应用
        └── SKILL.md

.cursor/
└── skills/
    └── ... (相同结构)

.codex/
└── skills/
    └── ... (相同结构)
```

每个 SKILL.md 包含：
- **frontmatter**: name, description（用于快速匹配）
- **后端应用详细内容**: API 清单、数据模型、外部依赖
- **前端应用详细内容**: 页面/组件清单、API 调用、状态管理、UI 组件库、路由配置

## 辅助脚本

### discover_apps.py

独立运行应用发现脚本：

```bash
# 基本用法（表格格式）
python3 skills/development/app-scanner/scripts/discover_apps.py

# 指定工作区
python3 skills/development/app-scanner/scripts/discover_apps.py /path/to/workspace

# 输出为 JSON
python3 skills/development/app-scanner/scripts/discover_apps.py --format json

# 输出为 Markdown（按类型分组）
python3 skills/development/app-scanner/scripts/discover_apps.py --format markdown

# 保存到文件
python3 skills/development/app-scanner/scripts/discover_apps.py --output apps.txt

# 排除特定目录
python3 skills/development/app-scanner/scripts/discover_apps.py --exclude tmp --exclude logs

# 仅生成到指定平台（默认：all）
python3 skills/development/app-scanner/scripts/discover_apps.py --target claude
python3 skills/development/app-scanner/scripts/discover_apps.py --target cursor
python3 skills/development/app-scanner/scripts/discover_apps.py --target claude --target cursor
```

**输出示例**（Markdown 格式）：

```markdown
# 发现的应用

## 后端应用

1. **cart-service**
   - 框架: `java-maven`
   - 路径: `services/cart`

2. **order-service**
   - 框架: `java-maven`
   - 路径: `services/order`

## 前端应用

1. **admin-frontend** ⚛️
   - 框架: `react`
   - 路径: `frontend/admin`

2. **customer-web** 💚
   - 框架: `vue`
   - 路径: `frontend/customer`
```

## 扫描内容详解

### 后端应用分析

#### 1. 业务描述

从以下信息源提取：
- README.md
- 包结构和模块命名
- Controller 类的业务功能
- 代码注释

生成包含：
- 应用职责
- 核心能力列表
- 典型业务场景
- 技术特征

#### 2. API 清单

扫描并提取：
- HTTP 方法（GET/POST/PUT/DELETE）
- 路径（/api/cart/{id}）
- 功能描述

#### 3. 数据模型

扫描并提取：
- 实体类（Entity）
- 字段名称和类型
- 实体间关系（一对一、一对多、多对多）

#### 4. 外部依赖

识别并分类：
- 应用依赖（其他微服务）
- RPC 调用（Dubbo/gRPC/REST）
- 基础设施依赖（MySQL/Redis/RabbitMQ）

### 前端应用分析

#### 1. 业务描述

从以下信息源提取：
- package.json（项目名称、描述）
- 目录结构（src/pages/, src/components/）
- 路由配置

生成包含：
- 应用职责
- 页面模块列表
- 典型交互场景
- 技术特征（框架 + UI 库 + 状态管理）

#### 2. 页面/组件清单

扫描并提取：
- 页面组件（src/pages/ 或 src/views/）
- 可复用组件（src/components/）
- 路由配置

#### 3. API 调用分析

扫描 src/api/ 或 src/services/ 目录，提取：
- API 端点路径
- HTTP 方法
- 请求参数

#### 4. 状态管理分析

识别使用的状态管理方案：
- Redux Toolkit (createStore, createSlice)
- Pinia (defineStore)
- Vuex (new Vuex.Store)
- Zustand (create)
- Context API (createContext)

#### 5. UI 组件库分析

从 package.json 依赖识别：
- Ant Design (antd)
- Material-UI (@mui/material)
- Chakra UI (@chakra-ui/react)
- Element Plus (element-plus)
- Vuetify (vuetify)
- Tailwind CSS (tailwindcss)

#### 6. 路由配置分析

提取前端路由结构：
- React Router: Route 组件配置
- Vue Router: routes 数组
- Angular: RouterModule.forRoot()
- Next.js/Nuxt.js: 文件系统路由

## 工作流程

```
用户输入: /scan-apps
    ↓
发现应用
  - 扫描工作区目录
  - 识别后端和前端项目
  - 生成应用列表
    ↓
扫描每个应用
  - 后端：业务描述 + API + 模型 + 依赖
  - 前端：页面组件 + API 调用 + 状态管理 + UI 库
    ↓
生成 SKILL.md
  - 同时写入 .claude/skills/
  - 同时写入 .cursor/skills/
  - 同时写入 .codex/skills/
    ↓
输出报告
  - 扫描成功/失败统计
  - 后端/前端应用分类
  - 下一步操作建议
```

## 错误处理

### 扫描失败

如果某个应用扫描失败：

```
❌ 扫描失败的应用

1. inventory-service
   - 路径: /workspace/inventory-service
   - 失败原因: pom.xml 文件损坏，无法解析
   - 建议: 检查 pom.xml 格式或手动创建 SKILL.md
```

**解决方法**：
1. 检查应用的构建文件（pom.xml/package.json）
2. 手动创建 SKILL.md
3. 修复后重新扫描

### 未找到应用

```
未找到任何应用

可能原因：
1. 工作区中没有符合识别特征的项目
2. 工作区路径不正确
3. 项目缺少必要的配置文件

建议：
1. 确认工作区路径是否正确
2. 检查项目是否包含 package.json/pom.xml/go.mod 等文件
3. 或使用 --add 参数手动添加应用
```

## 最佳实践

### 1. 首次扫描

在首次使用前，扫描所有应用：

```
/scan-apps
```

Review 生成的 SKILL.md，修正不准确的描述。

### 2. 定期更新

当应用有重大变更时，重新扫描：

```
/scan-apps --incremental
```

### 3. 手动修正

AI 生成的 description 可能不够准确，手动编辑 SKILL.md：

```markdown
---
name: cart-service
description: |
  # 修正后的描述（更准确）
---
```

### 4. 版本控制

将生成的目录加入版本控制：

```bash
git add .claude/skills/ .cursor/skills/ .codex/skills/
git commit -m "feat: 添加应用能力清单"
```

## 与其他技能的配合

### ai-pair-programmer

`app-scanner` 生成的 `SKILL.md` 可为结对开发提供应用上下文：

```
ai-pair-programmer
  ↓
读取 .claude/skills/*/SKILL.md (frontmatter)
  ↓
语义匹配 → 选择相关应用
  ↓
读取完整 SKILL.md (详细内容)
  ↓
实现并验证改动
```

### 通用开发流程

在项目初始化前，确保应用已被扫描：

```
开始开发任务
  ↓
检查 .claude/skills/ 是否存在
  ↓
如果不存在，提示运行 /scan-apps
```

## 故障排查

### 问题：扫描时间过长

**原因**：工作区包含大量文件

**解决**：
- 使用 `--incremental` 只扫描有变化的应用
- 排除不必要的目录：`--exclude tmp --exclude logs`

### 问题：生成的描述不准确

**原因**：代码结构不清晰或缺少文档

**解决**：
- 添加 README.md
- 改进代码注释
- 手动编辑 SKILL.md 的 description

### 问题：某些 API 未被识别

**原因**：动态生成的 API 或使用了反射

**解决**：
- 手动编辑 SKILL.md，添加缺失的 API
- 在代码中添加注释标记 API

## 相关文档

- [app-scanner 技能定义](../SKILL.md)
- [OpenSpec 官方文档](https://github.com/Fission-AI/OpenSpec)
