ages = [
    2,
    3,
    3,
    2,
    2,
    5,
    5,
    4,
    4,
    1,
    3,
    3,
    3,
    3,
    4,
    3,
    2,
    4,
    4,
    4,
    2,
    6,
    6,
    4,
    4,
    4,
    4,
    2,
    3,
    3,
    2,
    3,
    3,
    2,
    2
]
education = [
    3,
    4,
    5,
    4,
    2,
    3,
    2,
    4,
    6,
    3,
    4,
    4,
    4,
    4,
    3,
    4,
    3,
    4,
    3,
    2,
    2,
    3,
    1,
    3,
    4,
    4,
    5,
    4,
    4,
    4,
    4,
    4,
    4,
    4,
    4
]
monthly_incomes = [
    2,
    3,
    5,
    2,
    1,
    2,
    2,
    3,
    5,
    1,
    1,
    1,
    1,
    2,
    4,
    5,
    1,
    3,
    3,
    3,
    2,
    2,
    2,
    2,
    2,
    2,
    4,
    1,
    3,
    5,
    3,
    5,
    3,
    3,
    5
]

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, kruskal

# 数据
monthly_incomes = [
    2, 3, 5, 2, 1, 2, 2, 3, 5, 1, 1, 1, 1, 2, 4, 5, 1, 3, 3, 3, 2, 2, 2, 2, 2, 2, 4, 1, 3, 5, 3, 5, 3, 3, 5
]
improvements = [
    1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5
]

# 创建DataFrame
df = pd.DataFrame({
    'Improvement': improvements[:len(monthly_incomes)],  # 确保长度一致
    'Monthly_Income': monthly_incomes
})
print("数据预览：")
print(df.head())

# 描述性统计
print("\n描述性统计：")
grouped = df.groupby('Improvement')['Monthly_Income'].describe()
print(grouped)

# Mann-Whitney U检验
print("\nMann-Whitney U检验：")
group1 = df[df['Improvement'] == 1]['Monthly_Income']
group2 = df[df['Improvement'] == 2]['Monthly_Income']
stat, p = mannwhitneyu(group1, group2)
print(f"改进措施1 vs 改进措施2: 统计量={stat}, p值={p}")

# Kruskal-Wallis检验
print("\nKruskal-Wallis检验：")
groups = [df[df['Improvement'] == i]['Monthly_Income'] for i in df['Improvement'].unique()]
stat, p = kruskal(*groups)
print(f"所有改进措施的比较: 统计量={stat}, p值={p}")

# 可视化
plt.figure(figsize=(10, 6))
sns.boxplot(x='Improvement', y='Monthly_Income', data=df, palette='Set2')
plt.title('不同改进措施对月收入的影响')
plt.xlabel('改进措施')
plt.ylabel('月收入')
plt.show()