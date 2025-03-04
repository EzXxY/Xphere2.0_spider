import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows系统使用SimHei
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 读取数据  【改文件名称】
df = pd.read_excel("xphere2.0_holders_20250304_121929.xlsx")
df.sort_values("出块数量", ascending=False, inplace=True)

# 计算累计占比
total_blocks = df["出块数量"].sum()
df['累计占比'] = df["出块数量"].cumsum() / total_blocks * 100

# 自动计算覆盖80%算力的前N名
TOP_N = df[df['累计占比'] <= 80].shape[0] + 1
top_df = df.head(TOP_N)
other_blocks = df["出块数量"][TOP_N:].sum()
other_percent = other_blocks / total_blocks * 100

# 计算人数百分比
top_miner_percent = TOP_N / len(df) * 100
other_miner_percent = 100 - top_miner_percent

# 构建饼图数据
labels = [f"{i+1}" for i in range(TOP_N)] + [f'其他']  # 饼图内部只显示数字
legend_labels = [f"排名{i+1}" for i in range(TOP_N)] + [f'其他（{len(df)-TOP_N}名矿工）']  # 图例显示完整
sizes = list(top_df["出块数量"]) + [other_blocks]
explode = [0.05] * (TOP_N + 1)  # 轻微突出所有区块

# 设置专业配色方案
colors = plt.cm.tab20c.colors[:TOP_N+1]

# 创建画布
plt.figure(figsize=(12, 8), dpi=300)

# 绘制饼图（从0点开始顺时针排列）
patches, texts, autotexts = plt.pie(
    sizes,
    labels=labels,
    colors=colors,
    autopct='%1.1f%%',
    startangle=90,  # 从12点方向开始
    counterclock=False,  # 顺时针排列
    explode=explode,
    pctdistance=0.8,
    textprops={'fontsize': 10}
)

# 设置统一格式
plt.setp(autotexts, size=10, weight="bold", color="white")
plt.title(f"矿工出块数量分布（前{TOP_N}大矿工）\n总出块数：{total_blocks:,} | 矿工总数：{len(df)}", 
          fontsize=14, pad=20)
plt.axis('equal')  # 保证正圆形

# 添加图例
plt.legend(
    patches,
    legend_labels,
    title="矿工排名（出块数）",
    loc="center left",
    bbox_to_anchor=(1, 0.5),
    fontsize=9
)

# 添加统计信息
stats_text = (f"数据说明：\n"
              f"• 前{TOP_N}大矿工({top_miner_percent:.1f}%)合计占比总量的{100 - other_percent:.1f}%\n"
              f"• 其他{len(df)-TOP_N}名矿工({other_miner_percent:.1f}%)合计占比总量的{other_percent:.1f}%\n"
              f"• 数据来源：showdoll爬虫分析xp.tamsa.io区块浏览器")

plt.text(-1.5, -1.3, 
         stats_text,
         fontsize=9,
         ha='left')

# 保存图片
plt.tight_layout()
plt.savefig('Xphere2.0_80%.png', bbox_inches='tight')
print("图表已保存为 Xphere2.0_80%.png")