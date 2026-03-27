import json


input_path = 'datasheet.json'
output_path = 'datasheet.json'

with open(input_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if 'label_new' in item:
        del item['label_new']

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Đã xóa trường label_new khỏi datasheet.json!')
