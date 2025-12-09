# API 启动指南

## 问题修复

已修复以下问题：
1. ✅ 模块导入路径问题
2. ✅ 端口占用自动检测和切换

## 启动方法

### 方法 1：直接运行（推荐）

```bash
source venv/bin/activate
python src/api.py
```

API 会自动检测端口：
- 如果 5000 端口可用，使用 5000
- 如果 5000 被占用，自动使用 5001

### 方法 2：使用启动脚本

```bash
./start_api.sh
```

### 方法 3：指定端口

```bash
source venv/bin/activate
export FLASK_PORT=5001
python src/api.py
```

## 端口占用问题

### macOS 常见原因

macOS 的 **AirPlay Receiver** 默认使用端口 5000。

**解决方法：**
1. 打开 **系统设置** (System Settings)
2. 进入 **通用** (General) → **AirDrop 与隔空播放** (AirDrop & AirPlay)
3. 关闭 **隔空播放接收器** (AirPlay Receiver)

或者直接使用端口 5001（API 会自动切换）

### 检查端口占用

```bash
# 查看端口 5000 占用情况
lsof -i :5000

# 查看端口 5001 占用情况
lsof -i :5001
```

### 手动释放端口

```bash
# 找到占用端口的进程 ID
lsof -ti:5000

# 结束进程（替换 PID 为实际进程 ID）
kill -9 <PID>
```

## 验证 API 运行

启动后，在另一个终端运行：

```bash
# 健康检查
curl http://localhost:5000/health
# 或
curl http://localhost:5001/health
```

应该返回：
```json
{
  "status": "healthy",
  "service": "GC-REDSS"
}
```

## 前端配置

如果 API 运行在 5001 端口，需要更新前端配置：

在 `frontend` 目录创建 `.env` 文件：
```
VITE_API_URL=http://localhost:5001
```

或者修改 `frontend/vite.config.ts` 中的代理目标。

## 常见错误

### 1. ModuleNotFoundError: No module named 'src'
✅ **已修复** - 已添加路径处理

### 2. Address already in use
✅ **已修复** - 自动切换到 5001 端口

### 3. Spark 初始化慢
- 首次启动需要初始化 Spark，可能需要 10-30 秒
- 这是正常的，请耐心等待

### 4. 数据文件不存在
确保已运行数据下载脚本：
```bash
python scripts/download_data.py
```

