Big Data Final

Geo-Circle Based Interpretable Real Estate Decision Support System (GC-REDSS)

基于地理圈层与可解释评分的弹性房产决策辅助系统

---

https://www.kaggle.com/datasets/nelgiriyewithana/new-york-housing-market

2. Abstract

This project proposes the development of a novel Big Data-driven decision support system for real estate selection, addressing the rigid limitations of traditional search filters (e.g., Zillow). The core innovation lies in the use of **Static Isochrone Analysis (Geo-Circles)** calculated from public data (OpenStreetMap) to define flexible "Commute" and "Life" accessibility zones. Instead of hard filtering, the system employs a **transparent, weighted scoring model** to provide an adjustable $S$ score, allowing users to evaluate properties even if they fall just outside the defined circles—a concept we term "Elastic Filtering." The project will demonstrate advanced Geo-Spatial Big Data processing (Spark/GeoSpark), graph theory for network analysis (OSMnx), and model interpretability (SHAP/LIME) to provide deep, actionable insights for home buyers.

3. Keyword

Big Data, Geo-Spatial Analysis, Isochrone, Decision Support System, Graph Theory, Transparent Scoring, Elastic Filtering, SHAP/LIME.

4. Movtivation 

传统房产平台的筛选机制采用的是**硬性阈值（Hard Threshold）**：一旦房产价格超出预算一分钱或通勤时间超过一分钟，该房源就会被完全排除。这种**“非黑即白”**的筛选方式，使潜在用户错失了大量优质的、仅略微不符合要求的房源，决策僵化。

本项目旨在设计一个**弹性化、可视化、可解释**的决策系统，解决传统平台的僵化问题。

- **技术挑战：** 如何在不依赖昂贵商业 API 的情况下，利用 Big Data 技术（开源 Geo-Spatial 数据）精确构建**“静态通勤圈”**。
- **应用挑战：** 如何将复杂的地理空间分析结果融入一个**透明且可调节**的决策评分模型，辅助用户进行取舍。

5. 技术栈与方法论



6. 预期成果和贡献



- **数据获取**：API（如 Zillow、Google Places、NYC OpenData） + 静态 CSV/GeoJSON
- **数据处理**：Spark（清洗、合并、特征工程）
- **分析与建模**：PySpark ML（回归分析、聚类分析）
- **可视化**：Plotly + GeoJSON 地图（类似 sample 中的 subway map）
- **部署**：Docker + JupyterLab（可扩展为 Streamlit 或 Dash 应用）