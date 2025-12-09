# 快速启动指南

## 前置条件

1. **后端 API 必须运行**
2. **Node.js 和 npm 已安装**

## 启动步骤

### 1. 启动后端 API

```bash
# 在项目根目录
source venv/bin/activate
python src/api.py
```

后端将在 `http://localhost:5000` 运行

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 启动前端开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:3000` 运行

### 4. 打开浏览器

访问 `http://localhost:3000`

## 功能说明

### 搜索房产
1. 在左侧表单中输入工作地址（例如：Times Square, New York, NY）
2. 调整通勤时间阈值（默认 30 分钟）
3. 调整生活便利性阈值（默认 15 分钟）
4. 调整评分权重（可选）
5. 点击 "Search Properties" 按钮

### 查看房产
- **地图视图**：所有房产会以彩色标记显示在地图上
  - 🟢 绿色：高分（≥80%）
  - 🟠 橙色：中等（60-80%）
  - 🔴 红色：低分（<60%）

- **列表视图**：左侧显示所有房产列表，按分数排序

### 查看详情
- 点击地图上的标记或列表中的房产
- 右侧会显示详细信息面板，包括：
  - 房产基本信息
  - 评分雷达图
  - 评分柱状图
  - 各维度得分详情

## 故障排除

### 前端无法连接后端
- 确认后端 API 正在运行：`curl http://localhost:5000/health`
- 检查 `vite.config.ts` 中的代理配置

### 地图不显示
- 检查网络连接（需要加载 OpenStreetMap 瓦片）
- 检查浏览器控制台是否有错误

### 没有房产数据
- 确认后端已处理数据：检查 `data/processed/` 目录
- 确认后端 API 返回了数据：查看浏览器 Network 标签

