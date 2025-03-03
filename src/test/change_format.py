import json

# 1. 从 JSON 文件读取数据
input_file = r"D:\project\service\src\static\backend\test2.json"  # 输入文件名
output_file = "output_data.json"  # 输出文件名


with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)  # 读取 JSON 数据

# 2. 遍历数据并修改所有对象的 verified 字段
for item in data:
    if "credibility" in item and "verification" in item["credibility"]:
        item["credibility"]["verification"]["verified"] = True

# 3. 将修改后的数据写入新的 JSON 文件
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)  # 写入 JSON 文件

print(f"处理完成，结果已保存到 {output_file}")