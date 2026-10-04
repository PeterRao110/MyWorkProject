# MyWorkProject

前后端分离的网页项目。

- `frontend`：Vue 3 + TypeScript + Vite
- `backend`：Python + FastAPI

## 目录

```
MyWorkProject/
├── frontend/                 # 前端
│   ├── public/               # 静态资源
│   └── src/
│       ├── assets/           # 图片、字体等
│       ├── components/       # 可复用组件
│       ├── pages/            # 页面
│       ├── composables/      # 组合式函数
│       ├── services/         # 接口请求
│       ├── store/            # 状态
│       ├── styles/           # 全局样式
│       └── utils/            # 工具函数
└── backend/                  # 后端（FastAPI）
    ├── requirements.txt
    └── app/
        ├── main.py           # 应用入口
        ├── config/           # 配置
        ├── controllers/     # 控制器
        ├── routes/           # 路由
        ├── services/         # 业务逻辑
        ├── models/           # 数据模型
        ├── middleware/       # 中间件
        └── utils/            # 工具函数
```

## 启动

```bash
npm run install:all
npm run dev
```

- 前端：http://localhost:5173
- 后端：http://localhost:3000
- 健康检查：http://localhost:3000/api/health

## 数据库模型

模型变更按版本记在 [docs/database/模型变更记录.md](docs/database/模型变更记录.md)，并写入 MySQL 表 `schema_model_change`。

```bash
cd backend
python -m app.db.migrate
```

前端开发服务器会把 `/api` 代理到后端。
