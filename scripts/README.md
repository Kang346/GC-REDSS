# 数据获取脚本说明

## 使用方法

### 方法 1：直接运行脚本（推荐）

```bash
# 激活虚拟环境
source venv/bin/activate

# 安装 kagglehub（如果还没安装）
pip install kagglehub

# 运行下载脚本
python scripts/download_data.py
```

### 方法 2：在代码中自动下载

```python
from src.data_processor import DataProcessor
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("GC-REDSS").getOrCreate()
processor = DataProcessor(spark)

# 设置 auto_download=True 会自动下载缺失的数据集
properties_df = processor.load_raw_data(auto_download=True)
```

## 数据集信息

- **数据集名称**: New York Housing Market
- **Kaggle URL**: https://www.kaggle.com/datasets/nelgiriyewithana/new-york-housing-market
- **下载位置**: `data/raw/NY-House-Dataset.csv`

## 所需字段

数据集应包含以下字段：
- `ADDRESS` - 房产地址
- `PRICE` - 价格
- `BEDS` - 卧室数
- `BATH` - 浴室数
- `PROPERTYSQFT` - 平方英尺
- `LATITUDE` - 纬度
- `LONGITUDE` - 经度
- `TYPE` - 房产类型
- `ADMINISTRATIVE_AREA_LEVEL_2` - 行政区域
- `FORMATTED_ADDRESS` - 格式化地址

## 故障排除

### 问题：kagglehub 未安装
```bash
pip install kagglehub
```

### 问题：下载失败
1. 检查网络连接
2. 确认 Kaggle 数据集名称正确
3. 检查是否有足够的磁盘空间

### 问题：文件已存在
脚本会提示是否重新下载。输入 `y` 重新下载，输入 `n` 使用现有文件。



