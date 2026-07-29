---
name: app-scanner
description: 应用扫描与能力提取技能。扫描工作区中所有后端和前端应用（支持 Java/Go/Node.js/Python 及 React/Vue/Angular 等前端框架），分析代码结构，生成各应用的业务能力清单（业务描述、API清单、数据模型、外部依赖）。生成的技能文件同时支持 Claude Code (.claude/skills/)、Cursor (.cursor/skills/)、Codex (.codex/skills/) 三个目录，无需应用预先采用特定文档规范。
---

# 应用扫描与能力提取

## 技能概述

扫描工作区中所有应用（包括后端服务和前端项目），通过代码分析自动提取每个应用的业务能力，生成标准化的技能描述文件。

**多平台支持**：生成的 SKILL.md 文件格式兼容以下 AI 编程工具：
- **Claude Code**: `.claude/skills/`
- **Cursor**: `.cursor/skills/`
- **Codex**: `.codex/skills/`

支持自动识别项目类型，无需预先配置特定文档或开发规范。

## 何时使用

当以下情况时使用此技能：
- 首次设置开发环境，需要扫描所有应用
- 应用有重大更新，需要重新生成能力清单
- 新增了应用，需要将其加入应用目录
- 定期维护，保持应用能力清单的时效性

## 扫描范围

**目标应用**：工作区中满足以下任一条件的目录

### 后端应用识别
- 包含 `pom.xml` (Java/Maven)
- 包含 `build.gradle` 或 `build.gradle.kts` (Java/Gradle)
- 包含 `go.mod` (Go)
- 包含 `package.json` 且存在后端框架依赖 (Node.js)
- 包含 `requirements.txt`, `pyproject.toml`, `setup.py` (Python)

### 前端应用识别
- 包含 `package.json` 且满足以下任一条件：
  - 依赖包含 `react`, `react-dom`, `vue`, `vue-router`, `angular`, `@angular/core`
  - 依赖包含 `vite`, `webpack`, `rollup`, `parcel`, `esbuild`
  - 依赖包含 `next`, `nuxt`, `remix`, `svelte`, `solid`
- 包含前端配置文件：
  - `vite.config.js/ts`, `vue.config.js`, `angular.json`, `next.config.js`
  - `webpack.config.js`, `rollup.config.js`, `tailwind.config.js`
- 包含典型前端目录结构：
  - `src/pages/`, `src/components/`, `src/views/`
  - `public/`, `static/`, `assets/`

**排除目录**：
- `node_modules/` - 依赖目录
- `target/`, `build/`, `dist/`, `out/` - 构建输出目录
- `__pycache__/` - Python 缓存目录
- `.git/`, `.idea/`, `.vscode/` - IDE 和版本控制目录
- `vendor/` - 第三方依赖目录

## 工作流程

### Step 1: 发现应用

扫描工作区，识别所有后端和前端应用：

**方法 A: 基于用户指定的工作区根目录**
```
输入：工作区根目录（如 /workspace/IdeaProjects/retail）
扫描：递归查找所有符合识别特征的目录
输出：应用列表 [cart-service, order-service, admin-frontend, ...]
```

**方法 B: 基于当前目录**
```
从当前目录开始，向上查找第一个包含多个子项目的工作区根目录
然后扫描所有子项目
```

**发现逻辑**：
1. 递归扫描目录
2. 检查每个子目录是否符合后端或前端应用识别特征
3. 排除常见的非项目目录
4. 生成应用列表（包含类型、相对路径和绝对路径）

**应用分类**：
```
{
  name: "cart-service",
  type: "backend",
  framework: "spring-boot",
  path: "/path/to/cart-service"
}
{
  name: "admin-frontend",
  type: "frontend",
  framework: "react",
  path: "/path/to/admin-frontend"
}
```

### Step 2: 扫描每个应用

对每个应用进行多维度分析，根据应用类型（后端/前端）采用不同的分析策略。

---

#### 2.1 后端应用分析

**四维度分析**：

##### 2.1 业务描述分析

**目标**：生成一句话清晰描述应用的职责、核心能力、业务场景、技术特征

**信息来源**：
1. README.md（如果存在）
2. 包结构和模块命名
3. 主类或启动类
4. 代码注释和文档字符串

**分析步骤**：

**a) 读取 README.md**
```bash
优先查找：README.md, readme.md, README.zh.md
提取：
- 项目标题
- 项目简介
- 主要功能列表
```

**b) 分析包结构/目录结构**
```
示例：cart-service/
├── src/main/java/com/example/cart/
│   ├── controller/CartController.java
│   ├── service/CartService.java
│   ├── domain/Cart.java
│   └── repository/CartRepository.java

推断：
- 应用名称：购物车服务
- 核心领域：Cart（购物车）
- 分层架构：controller → service → repository
```

**c) 扫描 Controller/API 类**
```
识别业务能力：
- CartController → 购物车管理
- OrderController → 订单管理
- PaymentController → 支付管理
```

**d) 生成业务描述模板**
```
{应用名称}服务，负责{核心职责}。

核心能力：
- {能力1}（{简要说明}）
- {能力2}（{简要说明}）
- {能力3}（{简要说明}）

典型业务场景：
- {场景1}
- {场景2}

技术特征：{关键技术栈}
```

##### 2.2 API 清单分析

**目标**：提取所有对外暴露的 API 接口

**支持的项目类型**：

**Java (Spring Boot)**
```
扫描：@RestController, @Controller 类
提取：
- @RequestMapping, @GetMapping, @PostMapping 等注解
- 路径：/api/cart/{id}
- 方法：GET/POST/PUT/DELETE
- 参数：从方法签名和 @RequestParam, @PathVariable 提取
- 返回值：从返回类型和 @ResponseBody 提取
```

**Go (Gin/Echo/标准库)**
```
扫描：router 注册代码
识别模式：
- r.GET("/api/cart/:id", handler)
- router.POST("/api/cart", handler)
- http.HandleFunc("/api/cart", handler)
```

**Node.js (Express/Nest.js)**
```
扫描：
- Express: router.get('/api/cart', handler)
- Nest.js: @Get('/api/cart') 装饰器
- Fastify: fastify.get('/api/cart', handler)
```

**Python (Flask/Django)**
```
扫描：
- Flask: @app.route('/api/cart', methods=['GET'])
- Django: urlpatterns, @api_view
```

**输出格式**：
```markdown
## API 接口

### 购物车管理
- GET /api/cart/{id} - 查询购物车详情
- POST /api/cart/create - 创建购物车
- PUT /api/cart/{id} - 更新购物车
- DELETE /api/cart/{id} - 删除购物车

### 商品项管理
- POST /api/cart/add - 添加商品到购物车
- DELETE /api/cart/item/{itemId} - 删除商品项
- PUT /api/cart/item/{itemId} - 修改商品数量
```

##### 2.3 数据模型分析

**目标**：提取核心数据实体和关系

**支持的项目类型**：

**Java (JPA/MyBatis)**
```
扫描：@Entity, @Table 注解的类
提取：
- 类名 → 实体名
- @Id → 主键
- @Column → 字段（名称、类型）
- @OneToMany, @ManyToOne, @OneToOne → 关系
- @ManyToMany → 多对多关系
```

**Go (GORM/标准库)**
```
扫描：struct 定义
识别：包含 GORM 标签的 struct
提取：
- 字段名和类型
- gorm 标签（primaryKey, foreignKey等）
```

**Node.js (TypeScript/Prisma/Sequelize)**
```
扫描：
- Prisma schema.prisma
- Sequelize models
- TypeScript interfaces
```

**Python (SQLAlchemy/Django ORM)**
```
扫描：
- SQLAlchemy: class User(Base)
- Django: class User(models.Model)
提取：字段类型、关系
```

**输出格式**：
```markdown
## 数据模型

### Cart（购物车）
- id: string - 购物车ID
- userId: string - 用户ID
- items: CartItem[] - 商品项列表
- status: CartStatus - 购物车状态（TEMP/PERSISTENT）
- createdAt: datetime - 创建时间
- updatedAt: datetime - 更新时间

**关系**：
- 一对多：Cart → CartItem（一个购物车包含多个商品项）
- 多对一：Cart → User（多个购物车属于一个用户）
```

##### 2.4 外部依赖分析

**目标**：识别应用依赖的其他应用和服务

**信息来源**：

**a) 构建文件依赖**
```
Java (pom.xml):
- com.example.commerce:commerce-core
- org.springframework.boot:spring-boot-starter-web

Node.js (package.json):
- "@example/commerce-core": "^1.0.0"
- "express": "^4.18.0"
```

**b) RPC 调用识别**

**Dubbo (Java)**
```java
@Reference
private UserService userService;  // 依赖用户服务

@Reference
private ProductService productService;  // 依赖商品服务
```

**gRPC (多语言)**
```go
userClient := userpb.NewUserServiceClient(conn)  // 依赖用户服务
```

**REST Client**
```java
@RestController
public class CartController {
    @Autowired
    private RestTemplate restTemplate;  // 可能调用外部服务

    @GetMapping("/cart/{id}")
    public Cart getCart(@PathVariable String id) {
        // 检查是否有 HTTP 调用
        String url = "http://user-service/api/users/" + userId;
    }
}
```

**c) 配置文件**
```
application.yml:
dubbo:
  registry:
    address: zookeeper://localhost:2181
  references:
    userService:
      interface: com.example.commerce.user.UserService
```

**d) 数据库和中间件**
```
从依赖和配置识别：
- MySQL, PostgreSQL → 数据库依赖
- Redis → 缓存依赖
- RabbitMQ, Kafka → 消息队列依赖
```

**输出格式**：
```markdown
## 外部依赖

### 应用依赖
- commerce-core（商品服务）- Dubbo 调用
- identity-service（用户服务）- Dubbo 调用

### 基础设施依赖
- Redis（缓存）- 购物车数据缓存
- MySQL（数据库）- 购物车持久化
- RabbitMQ（消息队列）- 订单事件通知
```

---

#### 2.2 前端应用分析

**目标**：分析前端项目的页面结构、路由配置、API 调用、状态管理和 UI 组件

**信息来源**：

##### a) 业务描述分析

**目标**：生成前端应用的职责描述、页面模块和交互场景

**分析步骤**：

1. **读取 package.json**
```json
提取：
- 项目名称和描述
- 前端框架（react/vue/angular）
- 主要依赖和脚本命令
```

2. **分析目录结构**
```
示例：admin-frontend/
├── src/
│   ├── pages/          # 页面组件
│   │   ├── Dashboard/
│   │   ├── Cart/
│   │   └── Order/
│   ├── components/     # 可复用组件
│   ├── api/            # API 调用
│   ├── store/          # 状态管理
│   └── router/         # 路由配置

推断：
- 应用类型：后台管理系统
- 主要模块：Dashboard、购物车、订单
- 状态管理：可能有 Redux/Pinia/Vuex
```

3. **生成业务描述模板**
```
{应用名称}前端应用，负责{核心职责}。

页面模块：
- {模块1}（{简要说明}）
- {模块2}（{简要说明}）
- {模块3}（{简要说明}）

典型交互场景：
- {场景1}
- {场景2}

技术特征：{前端框架} + {UI组件库} + {状态管理方案}
```

##### b) 页面/组件清单

**目标**：提取所有页面和主要组件

**支持的项目类型**：

**React**
```
扫描：
- src/pages/ 或 src/views/ - 页面组件
- src/components/ - 可复用组件
- src/routes/ 或 src/router/ - 路由配置

识别模式：
- export default function CartPage()
- export const OrderList = ()
- React Router: <Route path="/cart" element={<Cart />} />
```

**Vue**
```
扫描：
- src/views/ 或 src/pages/ - 页面组件
- src/components/ - 可复用组件
- src/router/index.js - 路由配置

识别模式：
- export default { name: 'CartPage' }
- Vue Router: { path: '/cart', component: Cart }
```

**Angular**
```
扫描：
- src/app/pages/ - 页面组件
- src/app/components/ - 可复用组件
- src/app/app-routing.module.ts - 路由配置

识别模式：
- @Component({ selector: 'app-cart' })
- RouterModule: { path: 'cart', loadChildren: ... }
```

**Next.js/Nuxt.js**
```
扫描：
- app/ 或 pages/ - 文件路由
- components/ - 可复用组件

识别模式：
- app/cart/page.tsx (Next.js App Router)
- pages/cart.vue (Nuxt.js)
```

**输出格式**：
```markdown
## 页面/组件清单

### 页面模块
- /dashboard - 仪表盘首页
- /cart - 购物车管理页面
- /order/list - 订单列表页面
- /order/detail/:id - 订单详情页面

### 公共组件
- CartItem - 购物车商品项组件
- OrderCard - 订单卡片组件
- StatusBar - 状态栏组件
```

##### c) API 调用分析

**目标**：提取前端调用的后端 API

**信息来源**：

**src/api/ 或 src/services/ 目录**
```typescript
// 典型的 API 调用模式
export const cartApi = {
  getCart: (id: string) => request.get(`/api/cart/${id}`),
  addToCart: (data) => request.post('/api/cart/add', data),
  updateItem: (id, data) => request.put(`/api/cart/item/${id}`, data),
  deleteItem: (id) => request.delete(`/api/cart/item/${id}`)
}
```

**React Hooks**
```typescript
// React Query / SWR
const { data: cart } = useQuery(['cart', id], () => fetchCart(id))
const mutation = useMutation(updateCart)
```

**Vue Composition API**
```typescript
// VueUse / Vue Query
const { data } = useFetch(`/api/cart/${id}`).get().json()
```

**输出格式**：
```markdown
## API 调用清单

### 购物车相关
- GET /api/cart/{id} - 查询购物车
- POST /api/cart/add - 添加商品
- PUT /api/cart/item/{id} - 更新商品数量
- DELETE /api/cart/item/{id} - 删除商品

### 订单相关
- GET /api/order/list - 订单列表
- GET /api/order/{id} - 订单详情
- POST /api/order/create - 创建订单
```

##### d) 状态管理分析

**目标**：识别前端使用的状态管理方案

**支持的状态管理**：

**Redux Toolkit**
```
扫描：src/store/ 或 src/redux/
识别：
- configureStore()
- createSlice()
- useSelector(), useDispatch()
```

**Pinia (Vue 3)**
```
扫描：src/stores/ 或 src/store/
识别：
- defineStore()
- useCartStore()
```

**Vuex (Vue 2)**
```
扫描：src/store/
识别：
- new Vuex.Store()
- mapState(), mapActions()
```

**Zustand**
```
扫描：src/store/
识别：
- create()
- useStore()
```

**Context API (React)**
```
扫描：src/contexts/
识别：
- createContext()
- useContext()
```

**输出格式**：
```markdown
## 状态管理

### 方案
- Redux Toolkit (React)

### Store 结构
- cartStore - 购物车状态
- orderStore - 订单状态
- userStore - 用户状态
```

##### e) UI 组件库分析

**目标**：识别使用的 UI 组件库

**识别方式**：

**从 package.json 依赖识别**
```
- antd → Ant Design
- @mui/material → Material-UI
- @chakra-ui/react → Chakra UI
- element-plus → Element Plus (Vue)
- vuetify → Vuetify (Vue)
- @angular/material → Angular Material
- tailwindcss → Tailwind CSS
```

**输出格式**：
```markdown
## UI 组件库

- Ant Design 5.x
- Tailwind CSS 3.x
- 自定义组件库 @company/ui-components
```

##### f) 路由配置分析

**目标**：提取前端路由结构

**React Router**
```typescript
// 扫描路由配置文件
const routes = [
  { path: '/dashboard', element: <Dashboard /> },
  { path: '/cart', element: <Cart /> },
  { path: '/order/:id', element: <OrderDetail /> }
]
```

**Vue Router**
```javascript
const routes = [
  { path: '/dashboard', component: Dashboard },
  { path: '/cart', component: Cart },
  { path: '/order/:id', component: OrderDetail }
]
```

**输出格式**：
```markdown
## 路由配置

- /dashboard → Dashboard 页面
- /cart → 购物车页面
- /order/list → 订单列表
- /order/detail/:id → 订单详情
```

### Step 3: 生成技能文件

为每个应用生成独立的技能文件，**默认同时生成到所有支持的 AI 编程工具目录**：

**输出目录**（默认全部生成）：
- `.claude/skills/<app-name>/SKILL.md` - Claude Code
- `.cursor/skills/<app-name>/SKILL.md` - Cursor
- `.codex/skills/<app-name>/SKILL.md` - Codex

**后端应用文件结构**:
```markdown
---
name: cart-service
description: |
  购物车服务，负责用户的购物车管理。

  核心能力：
  - 购物车 CRUD 操作（创建、查询、更新、删除购物车）
  - 商品项管理（添加商品、删除商品、修改数量）
  - 购物车计算（商品总价、促销优惠、运费计算）
  - 购物车状态管理（临时购物车、持久化购物车）

  典型业务场景：
  - 用户浏览商品时添加到购物车
  - 用户在购物车页面修改商品数量
  - 用户结算时读取购物车明细
  - 购物车数据同步到订单系统

  技术特征：基于 Redis 缓存 + MySQL 持久化
---

# 应用能力详情

## API 接口
{从 Step 2.2 提取的 API 清单}

## 数据模型
{从 Step 2.3 提取的数据模型}

## 外部依赖
{从 Step 2.4 提取的外部依赖}

## 扫描元数据
- 应用类型: backend
- 扫描时间: {ISO 8601 时间戳}
- 扫描版本: {app-scanner 版本}
- 项目路径: {应用绝对路径}
```

**前端应用文件结构**:
```markdown
---
name: admin-frontend
description: |
  后台管理前端应用，提供运营后台管理界面。

  页面模块：
  - 仪表盘（数据概览、快捷操作）
  - 购物车管理（购物车列表、商品项管理）
  - 订单管理（订单列表、订单详情、订单状态流转）

  典型交互场景：
  - 用户登录后台查看数据概览
  - 管理购物车商品和价格
  - 处理订单和发货

  技术特征：React 18 + Ant Design 5 + Redux Toolkit + React Router 6
---

# 应用能力详情

## 页面/组件清单
{从 Step 2.5-b 提取的页面组件}

## API 调用清单
{从 Step 2.5-c 提取的 API 调用}

## 状态管理
{从 Step 2.5-d 提取的状态管理方案}

## UI 组件库
{从 Step 2.5-e 提取的 UI 组件库}

## 路由配置
{从 Step 2.5-f 提取的路由结构}

## 扫描元数据
- 应用类型: frontend
- 扫描时间: {ISO 8601 时间戳}
- 扫描版本: {app-scanner 版本}
- 项目路径: {应用绝对路径}
```

### Step 4: 输出扫描报告

生成扫描摘要报告：

```markdown
# 应用扫描报告

## 扫描概览
- 扫描时间: 2026-01-28T10:00:00Z
- 工作区: /workspace/IdeaProjects/retail
- 发现应用: 5 个
- 成功扫描: 4 个
- 扫描失败: 1 个

## 扫描结果

### ✅ 成功扫描的应用

1. **cart-service**
   - 路径: /workspace/cart-service
   - 业务描述: 购物车服务，负责用户的购物车管理
   - API 数量: 12 个
   - 数据模型: 2 个
   - 外部依赖: 3 个

2. **order-service**
   - 路径: /workspace/order-service
   - 业务描述: 订单服务，负责订单创建、支付、履约
   - API 数量: 18 个
   - 数据模型: 5 个
   - 外部依赖: 4 个

...

### ❌ 扫描失败的应用

1. **inventory-service**
   - 路径: /workspace/inventory-service
   - 失败原因: pom.xml 文件损坏，无法解析
   - 建议: 检查 pom.xml 格式或手动创建 SKILL.md

## 下一步操作
- 查看生成的技能文件: .claude/skills/
- 修复扫描失败的应用后重新扫描
- 使用 `ai-pair-programmer` 开始开发
```

## 技术实现要点

### 1. 灵活的代码解析

**原则**：不要硬编码特定框架的规则，使用 AI 理解代码

**实现**：
- 识别项目类型（Java/Go/Node.js/Python）
- 根据项目类型选择合适的扫描策略
- 对于复杂的代码结构，使用 AI 进行语义分析

**示例提示词**：
```
分析以下 Java 类的业务功能：
{CartController 的源代码}

请提取：
1. 这个类提供的业务能力（如购物车管理）
2. 每个方法的用途（如 getCart - 查询购物车）
3. 对外暴露的 API 接口（路径、HTTP 方法）
```

### 2. 增量扫描

**目的**：避免重复扫描未变化的应用

**实现**：
1. 记录每个应用的最后扫描时间
2. 检查关键文件的修改时间：
   - `pom.xml`, `package.json`, `go.mod` - 依赖变化
   - `src/main/java/**/*Controller.java` - API 变化
   - `src/main/java/**/*Entity.java` - 模型变化
3. 只有当关键文件有更新时才重新扫描

**伪代码**：
```python
def should_scan(app_path, last_scan_time):
    key_files = [
        'pom.xml', 'package.json',
        '**/*Controller.java', '**/*Entity.java'
    ]
    for file in key_files:
        if get_mtime(file) > last_scan_time:
            return True
    return False
```

### 3. 错误恢复

**原则**：单个应用扫描失败不应影响其他应用

**实现**：
- try-catch 包裹每个应用的扫描逻辑
- 记录错误信息，继续扫描下一个应用
- 最终报告中列出失败的应用和建议

**示例**：
```python
scan_results = {
    'success': [],
    'failed': []
}

for app in apps:
    try:
        result = scan_app(app)
        scan_results['success'].append(result)
    except Exception as e:
        scan_results['failed'].append({
            'app': app,
            'error': str(e),
            'suggestion': get_suggestion(e)
        })
```

### 4. 多语言与框架支持

**后端项目类型**：
- Java: Maven (pom.xml), Gradle (build.gradle)
- Go: go.mod
- Node.js: package.json (后端框架)
- Python: requirements.txt, pyproject.toml, setup.py

**前端项目类型**：
- React: Create React App, Vite, Next.js
- Vue: Vue CLI, Vite, Nuxt.js
- Angular: Angular CLI
- Svelte: SvelteKit
- 其他: Solid.js, Remix, Astro

**扩展性**：
- 插件化的扫描器架构
- 每种语言/框架实现独立的 Scanner 接口
- 新增框架只需添加新的 Scanner

## 使用示例

### 基本用法

```
用户: /scan-apps

AI: 开始扫描工作区中的所有应用...

[扫描过程]
✓ 发现 5 个应用
✓ 扫描 cart-service
✓ 扫描 order-service
✓ 扫描 commerce-core
✓ 扫描 identity-service
✗ 扫描 inventory-service 失败

[输出结果]
扫描完成！
- 成功: 4 个应用
- 失败: 1 个应用

生成的技能文件：
- .claude/skills/cart-service/SKILL.md
- .claude/skills/order-service/SKILL.md
- .claude/skills/commerce-core/SKILL.md
- .claude/skills/identity-service/SKILL.md
- .cursor/skills/cart-service/SKILL.md
- .cursor/skills/order-service/SKILL.md
- ...

查看完整报告: 扫描报告已显示在上方

下一步：
- 修复 inventory-service 后重新扫描
- 使用 `ai-pair-programmer` 开始开发
```

### 指定工作区

```
用户: /scan-apps /workspace/IdeaProjects/retail

AI: 扫描指定工作区: /workspace/IdeaProjects/retail
...
```

### 仅生成到指定平台

```
用户: /scan-apps --target claude

AI: 仅生成到 Claude Code 目录...
```

### 增量扫描

```
用户: /scan-apps --incremental

AI: 检查应用变更...
- cart-service: 有变更（3 天前更新）
- order-service: 无变更（跳过）
- commerce-core: 无变更（跳过）

只扫描有变更的应用...
✓ 扫描 cart-service

完成！1 个应用已更新
```

## 注意事项

- ⚠️ **首次扫描**: 首次扫描可能需要较长时间，请耐心等待
- ⚠️ **扫描频率**: 建议每周或每次重大变更后重新扫描
- ⚠️ **手动修正**: AI 生成的 description 可能不够准确，建议用户 review 并手动修正
- ⚠️ **依赖分析**: 外部依赖分析可能不完整，特别是通过配置文件或间接调用的依赖
- ⚠️ **API 提取**: 动态生成的 API（如通过反射、路由自动注册）可能无法识别
- ⚠️ **多平台同步**: 默认同时生成到三个平台，确保各平台目录的写入权限

## 与其他技能的集成

### sdd-dev-workflow

- 提供应用职责、接口、数据模型和外部依赖证据
- 用于确认技术方案的影响应用、跨应用依赖和实施顺序

### ai-pair-programmer

- **读取** `.claude/skills/*/SKILL.md` 的 frontmatter
- 用于应用匹配和候选应用列表生成

### 通用开发流程

- 在项目初始化前，确保应用已被扫描
- 提示用户运行 `/scan-apps` 如果 `.claude/skills/`（或 `.cursor/skills/` / `.codex/skills/`）目录不存在
