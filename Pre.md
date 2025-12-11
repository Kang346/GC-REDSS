# Data Processing Pipeline

## 1. New York Housing Market Dataset

### 1.1 Data Acquisition
The dataset is downloaded from Kaggle. The script is in the `scripts` directory, or you can download it manually from the Kaggle website and place it in the `data/raw` directory.

### 1.2 Data Processing

#### 1.2.1 Data Cleaning - Spark 分布式数据处理思想

我们使用 **PySpark** 进行数据清洗，这体现了几个重要的大数据处理思想：

**1. 分布式并行处理**
- Spark 将数据自动分区（partition）到多个节点上
- 每个分区的数据清洗操作可以并行执行
- 相比单机处理，可以显著提升处理速度

**2. 延迟执行（Lazy Evaluation）**
- Spark 的转换操作（transformation）是延迟执行的
- 只有在遇到行动操作（action）时才会真正执行
- 这允许 Spark 优化整个执行计划，减少不必要的中间结果

**3. 列式操作优化**
- 使用 Spark SQL 的列式操作，而不是逐行处理
- 利用 Catalyst 优化器进行查询优化

代码示例展示了如何使用 Spark 的列式操作进行数据清洗：

```python
# Clean and standardize columns
df = df.withColumn("PRICE", 
    when(col("PRICE").isNull() | (col("PRICE") <= 0), None)
    .otherwise(col("PRICE")))

df = df.withColumn("BEDS",
    when(col("BEDS").isNull() | (col("BEDS") < 0), None)
    .otherwise(col("BEDS").cast(IntegerType())))

df = df.withColumn("BATH",
    when(col("BATH").isNull() | (col("BATH") < 0), None)
    .otherwise(col("BATH").cast(DoubleType())))

df = df.withColumn("PROPERTYSQFT",
    when(col("PROPERTYSQFT").isNull() | (col("PROPERTYSQFT") <= 0), None)
    .otherwise(col("PROPERTYSQFT").cast(DoubleType())))

# Clean address fields
df = df.withColumn("ADDRESS", trim(col("ADDRESS")))
df = df.withColumn("FORMATTED_ADDRESS", trim(col("FORMATTED_ADDRESS")))

# Ensure latitude and longitude are valid
df = df.withColumn("LATITUDE",
    when((col("LATITUDE").isNull()) | 
         (col("LATITUDE") < -90) | (col("LATITUDE") > 90), None)
    .otherwise(col("LATITUDE").cast(DoubleType())))

df = df.withColumn("LONGITUDE",
    when((col("LONGITUDE").isNull()) | 
         (col("LONGITUDE") < -180) | (col("LONGITUDE") > 180), None)
    .otherwise(col("LONGITUDE").cast(DoubleType())))

# Filter out records without essential geospatial data
df = df.filter(
    col("LATITUDE").isNotNull() & 
    col("LONGITUDE").isNotNull() &
    col("PRICE").isNotNull()
)
```

**技术要点：**
- `withColumn()`: 创建新列或修改现有列，支持并行处理
- `when().otherwise()`: 条件表达式，在 Spark 中会被优化为高效的列式操作
- `filter()`: 分布式过滤，只保留满足条件的记录
- 所有操作都是**不可变的（immutable）**，每次转换都返回新的 DataFrame

#### 1.2.2 Data Engineering - 特征工程的分布式计算

特征工程同样利用 Spark 的分布式计算能力，体现了**数据并行(Data Parallelism)**的思想：

```python
# Calculate price per square foot
df = df.withColumn(
    "PRICE_PER_SQFT",
    when(col("PROPERTYSQFT").isNotNull() & (col("PROPERTYSQFT") > 0),
         col("PRICE") / col("PROPERTYSQFT"))
    .otherwise(None)
)

# Calculate bedrooms per bathroom ratio
df = df.withColumn(
    "BEDS_PER_BATH",
    when(col("BATH").isNotNull() & (col("BATH") > 0),
         col("BEDS") / col("BATH"))
    .otherwise(None)
)

# Create property type category
df = df.withColumn(
    "PROPERTY_TYPE_CLEAN",
    lower(regexp_replace(col("TYPE"), r"\s+", "_"))
)

# Extract borough from administrative area
df = df.withColumn(
    "BOROUGH",
    when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Manhattan"), "Manhattan")
    .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Kings"), "Brooklyn")
    .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Queens"), "Queens")
    .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Richmond"), "Staten Island")
    .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Bronx"), "Bronx")
    .otherwise(col("ADMINISTRATIVE_AREA_LEVEL_2"))
)
```

**技术要点：**
- 所有特征计算都是**向量化操作**，在 Spark 中并行执行
- 使用 Spark SQL 的内置函数（`lower()`, `regexp_replace()`, `contains()`）进行字符串处理
- 条件逻辑使用 `when().otherwise()` 链式调用，Spark 会优化为高效的执行计划

#### 1.2.3 数据存储：Parquet 列式存储格式

我们使用 **Parquet** 格式存储处理后的数据，这体现了大数据存储的重要思想：

**1. 列式存储的优势**
- **压缩率高**：相同类型的数据存储在一起，压缩效率更高（通常比 CSV 小 10-100 倍）
- **查询性能好**：只读取需要的列，减少 I/O
- **模式演化**：支持添加新列而不影响现有数据

**2. Spark 与 Parquet 的集成**
```python
# Save processed data
df.write.mode("overwrite").parquet(output_path)

# Load processed data
df = self.spark.read.parquet(file_path)
```

**3. 缓存策略**
- 处理后的数据保存为 Parquet，避免重复处理
- 加载时先检查是否存在处理后的数据，体现了**缓存优先**的思想

```python
def get_processed_data(self, file_path: str = None) -> 'DataFrame':
    if file_path is None:
        file_path = str(PROCESSED_DATA_DIR / "processed_houses.parquet")
    
    logger.info(f"Loading processed data from {file_path}")
    df = self.spark.read.parquet(file_path)
    return df
```

**技术要点：**
- Parquet 是 Spark 的原生格式，读写性能优异
- 支持**谓词下推（Predicate Pushdown）**：在读取时就可以过滤数据
- 支持**列裁剪（Column Pruning）**：只读取查询需要的列

#### 1.2.4 Few Q&A
为什么选择这个数据？因为这个数据比较全,有我们需要的各种字段.

为什么不选用多源数据进行join然后处理?我找了一些其他数据,很多存在各种各样的问题,比如有的数据大量条目没有价格(NYC Property Sales),有的数据只有房屋的简略信息,没有面积,几个卧室等.
这是因为我们要做的假设我们有现在挂牌的房屋,然后为用户提供搜索结果,但很多数据是过去房屋的销售信息,关注的点不同,所以缺少有些关键的条目.

## 2. Geo-Circle Calculation

### 2.1 技术选择：单机图计算 vs Spark GraphX

我们使用了 **OSMnx** 库来下载路网数据，使用 **NetworkX** 库来计算最短路径。这是一个重要的技术决策，体现了**任务特性决定技术选型**的思想。

#### 2.1.1 为什么不用 Spark GraphX？

**1. 数据规模考虑**
- 即使在曼哈顿这样复杂的路网下，设置通勤时间为 1 小时，需要计算的节点也不会超过 100 万个
- 这个规模在单机内存中可以轻松处理（通常 < 1GB）
- 使用 Spark GraphX 会带来**不必要的开销**：
  - 网络通信开销
  - 序列化/反序列化开销
  - 任务调度开销

**2. 计算特性分析**
图的最短路径计算是一个**高度相互依赖的计算**：
- Dijkstra 算法需要按距离顺序访问节点
- 每个节点的计算依赖于前一个节点的结果
- 这种**顺序依赖**使得并行化困难

如果使用 Spark GraphX：
- 需要进行大量的 **shuffle** 操作（数据重分布）
- 每轮迭代都需要网络通信
- 对于这种小规模、高依赖的图计算，**单机算法更高效**

**3. 批量计算优化**
我们使用了 NetworkX 的批量最短路径算法，而不是逐个计算：

```python
# OPTIMIZED: Use batch shortest path algorithm (Dijkstra) instead of iterating all nodes
# This calculates all shortest paths from center_node at once, much faster than looping
cutoff_with_buffer = max_time_seconds * 1.2  # 1.2x buffer
path_lengths = nx.single_source_dijkstra_path_length(
    G, center_node, weight='travel_time', cutoff=cutoff_with_buffer
)
# Filter to only include nodes within actual time limit
travel_times = {node: length for node, length in path_lengths.items() 
               if length <= max_time_seconds}
```

**技术要点：**
- `single_source_dijkstra_path_length()`: 一次性计算从源点到所有可达节点的最短路径
- 使用 `cutoff` 参数限制搜索范围，提高效率
- 这是**单源最短路径**的经典算法，在单机上执行效率最高

### 2.2 Geo-Circle Calculation 流程

**1. 路网数据获取**
- 使用 OSMnx 从 OpenStreetMap 下载路网数据
- 根据交通模式（driving, walking, transit, biking, subway）下载不同的路网类型
- 路网数据被缓存，避免重复下载

**2. 最短路径计算**
- 使用 Dijkstra 算法计算从工作地点到所有可达节点的最短路径
- 根据交通模式使用不同的速度参数
- 生成等时圈（isochrone）多边形

**3. 结果缓存**
- 计算出的等时圈被缓存到磁盘
- 相同参数的查询可以直接使用缓存结果
- 体现了**计算复用**的思想

## 3. Scoring Model - 分布式并行评分

### 3.1 并行化策略：从串行到分布式

在计算每个房屋的分数时，我们使用了 **Spark UDF（User Defined Function）** 来并行计算。这体现了**任务并行（Task Parallelism）**的思想。

#### 3.1.1 为什么需要并行化？

**原始问题：**
- 每个房屋的分数计算是**独立的**（embarrassingly parallel）
- 如果使用串行 for 循环，处理 5000 个房屋需要很长时间
- 随着数据规模增长，串行处理会成为瓶颈

**解决方案：**
- 使用 Spark 将房屋数据分布到多个节点
- 每个节点并行计算分配给它的房屋分数
- 充分利用多核 CPU 和分布式集群资源

#### 3.1.2 Spark UDF 的实现

**1. UDF 创建**
```python
def _create_commute_score_udf(self, commute_circles: Dict[str, any], 
                               commute_threshold: float):
    """
    Create Spark UDF for calculating commute scores in parallel
    """
    # Serialize polygons for transmission to Spark workers
    commute_circles_serialized = {}
    for mode, circle in commute_circles.items():
        if circle is not None:
            commute_circles_serialized[mode] = self._serialize_polygon(circle)
    
    def calculate_commute_score_udf(lat: float, lon: float) -> float:
        """UDF function to calculate commute score"""
        import math
        import pickle
        import base64
        from shapely.geometry import Point
        from geopy.distance import geodesic
        
        # ... 计算逻辑 ...
        
        return score
    
    return udf(calculate_commute_score_udf, DoubleType())
```

**2. UDF 应用**
```python
# Calculate commute score using Spark UDF (parallel processing)
commute_score_udf = self._create_commute_score_udf(
    commute_circles, 
    commute_threshold_minutes
)
result_df = result_df.withColumn(
    "commute_score",
    commute_score_udf(col("LATITUDE"), col("LONGITUDE"))
)
```

**技术要点：**
- UDF 函数会被序列化并发送到各个 Spark worker 节点
- 每个 worker 节点独立处理分配给它的数据分区
- Spark 自动处理任务调度、容错和结果聚合

#### 3.1.3 对象序列化：跨节点数据传输

**问题：**
- Shapely Polygon 对象无法直接在 Spark 节点间传输
- 需要将对象序列化为可传输的格式

**解决方案：**
```python
def _serialize_polygon(self, polygon) -> str:
    """
    Serialize Shapely Polygon to base64-encoded pickle string for Spark UDF
    """
    if polygon is None:
        return None
    return base64.b64encode(pickle.dumps(polygon)).decode('utf-8')

def _deserialize_polygon(self, polygon_str: str):
    """
    Deserialize base64-encoded pickle string back to Shapely Polygon
    """
    if polygon_str is None:
        return None
    return pickle.loads(base64.b64decode(polygon_str.encode('utf-8')))
```

**序列化流程：**
1. **Driver 节点**：使用 `pickle.dumps()` 将 Polygon 对象序列化为二进制
2. **编码**：使用 `base64.b64encode()` 编码为字符串（便于传输）
3. **传输**：字符串随 UDF 代码一起发送到 worker 节点
4. **Worker 节点**：反序列化回 Polygon 对象，用于计算

**技术要点：**
- 序列化是分布式计算中的关键技术
- 需要确保序列化的对象可以在 worker 节点上正确反序列化
- 使用 base64 编码确保字符串传输的可靠性

#### 3.1.4 特征归一化的分布式聚合

对于特征归一化，我们使用 Spark 的**分布式聚合**操作：

```python
def _normalize_feature_spark(self, df: DataFrame, col_name: str, 
                              reverse: bool = False) -> DataFrame:
    """
    Normalize a feature column using Spark operations (parallel)
    """
    # Calculate min and max using Spark aggregations (parallel)
    stats = df.select(
        spark_min(col(col_name)).alias("min_val"),
        spark_max(col(col_name)).alias("max_val")
    ).collect()[0]
    
    min_val = stats["min_val"]
    max_val = stats["max_val"]
    
    # Normalize: (value - min) / (max - min)
    normalized = (col(col_name) - lit(min_val)) / lit(max_val - min_val)
    
    if reverse:
        normalized = lit(1.0) - normalized
    
    # Clip to [0, 1]
    normalized = when(normalized < 0, 0.0).when(normalized > 1, 1.0).otherwise(normalized)
    
    return df.withColumn(f"{col_name.lower()}_score", normalized)
```

**技术要点：**
- `spark_min()` 和 `spark_max()` 是**分布式聚合**操作
- Spark 会在每个分区上计算局部 min/max，然后聚合得到全局值
- 归一化操作是**向量化的**，对所有行并行执行

#### 3.1.5 性能对比

**串行处理（原始方案）：**
```python
# 串行 for 循环
commute_scores = []
for idx, row in properties_pd.iterrows():
    score = self.calculate_commute_score(...)
    commute_scores.append(score)
```
- 处理 5000 个房屋：~30-60 秒
- 无法利用多核 CPU
- 无法扩展到分布式集群

**并行处理（Spark UDF）：**
```python
# Spark UDF 并行处理
result_df = result_df.withColumn(
    "commute_score",
    commute_score_udf(col("LATITUDE"), col("LONGITUDE"))
)
```
- 处理 5000 个房屋：~5-10 秒（在 4 核机器上）
- 充分利用多核 CPU
- 可以轻松扩展到分布式集群，性能线性提升

### 3.2 Spark 配置优化

我们配置了 Spark 以优化性能：

```python
spark = SparkSession.builder \
    .appName(SPARK_CONFIG["spark.app.name"]) \
    .config("spark.sql.warehouse.dir", SPARK_CONFIG["spark.sql.warehouse.dir"]) \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .getOrCreate()
```

**关键配置：**
- **Arrow 优化**：`spark.sql.execution.arrow.pyspark.enabled` 启用 Apache Arrow，加速 Python 和 JVM 之间的数据交换
- **自适应执行**：`spark.sql.adaptive.enabled` 启用自适应查询执行，动态优化执行计划
- **分区合并**：`spark.sql.adaptive.coalescePartitions.enabled` 自动合并小分区，减少任务数量

## 4. 整体架构设计思想

### 4.1 混合计算架构

我们的系统采用了**混合计算架构**：
- **单机计算**：用于图计算（等时圈计算），因为数据规模小、依赖性强
- **分布式计算**：用于数据清洗和评分计算，因为数据规模大、任务独立

这体现了**根据任务特性选择合适技术**的思想。

### 4.2 数据流水线设计

```
原始 CSV 数据
    ↓
[Spark 分布式清洗] ← 利用 Spark 的并行处理能力
    ↓
[特征工程] ← 向量化操作，并行执行
    ↓
Parquet 存储 ← 列式存储，高效压缩
    ↓
[单机图计算] ← 等时圈计算，单机更高效
    ↓
[Spark UDF 并行评分] ← 分布式评分计算
    ↓
结果输出
```

### 4.3 缓存策略

- **数据缓存**：处理后的数据保存为 Parquet，避免重复处理
- **计算结果缓存**：等时圈计算结果缓存到磁盘
- **Spark 会话复用**：在 API 服务中复用 Spark 会话，避免重复初始化

### 4.4 可扩展性设计

- **水平扩展**：Spark 可以轻松扩展到更多节点
- **数据分区**：Spark 自动处理数据分区和任务分配
- **容错机制**：Spark 的容错机制确保任务失败时自动重试

## 5. 总结

本项目展示了以下大数据技术和思想：

1. **分布式数据处理**：使用 Spark 进行数据清洗和特征工程
2. **列式存储**：使用 Parquet 格式优化存储和查询
3. **任务并行化**：使用 Spark UDF 实现并行评分计算
4. **对象序列化**：解决分布式计算中的对象传输问题
5. **混合计算架构**：根据任务特性选择单机或分布式计算
6. **延迟执行和查询优化**：利用 Spark 的 Catalyst 优化器
7. **缓存策略**：多层次缓存提升性能

这些技术的应用使得系统能够高效处理大规模房产数据，同时保持代码的简洁和可维护性。
