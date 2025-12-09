# 前端启动指南

## 快速启动

### 1. 启动后端 API

```bash
# 在项目根目录
source venv/bin/activate
python src/api.py
```

**注意**：查看启动日志，确认 API 使用的端口（可能是 5002, 5003 等）

### 2. 配置前端 API 地址

如果 API 运行在非 5002 端口，需要更新前端配置：

**方法 1：创建 .env 文件（推荐）**

```bash
cd frontend
cp .env.example .env
# 编辑 .env 文件，设置正确的端口
# 例如：VITE_API_URL=http://localhost:5003
```

**方法 2：修改 vite.config.ts**

直接修改 `frontend/vite.config.ts` 中的代理目标端口

### 3. 安装依赖并启动

```bash
cd frontend
npm install
npm run dev
```

### 4. 打开浏览器

访问 `http://localhost:3000`

## 端口说明

后端 API 会自动尝试以下端口：
- 5000（默认，但可能被 AirPlay 占用）
- 5001（备用）
- 5002（备用，前端默认使用此端口）
- 5003, 5004, 5005（其他备用端口）

启动 API 时，查看日志中的端口信息，然后更新前端配置。

## 故障排除

### 前端无法连接后端

1. **检查后端是否运行**
   ```bash
   curl http://localhost:5002/health
   # 或尝试其他端口
   ```

2. **检查端口是否匹配**
   - 查看后端启动日志中的端口
   - 确保前端 `.env` 或 `vite.config.ts` 中的端口一致

3. **检查 CORS**
   - 后端已启用 CORS，应该不会有问题
   - 如果还有问题，检查浏览器控制台的错误信息

### 地图不显示

- 检查网络连接（需要加载 OpenStreetMap 瓦片）
- 检查浏览器控制台是否有错误

