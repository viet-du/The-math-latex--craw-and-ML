import json

# Đường dẫn file
input_path = 'formulas/datasheet_relabel.json'
output_path = 'formulas/datasheet.json'

with open(input_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Thay thế trường 'label' bằng 'label_new'
for item in data:
    if 'label_new' in item:
        item['label'] = item['label_new']

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Đã đồng bộ label từ label_new sang label trong datasheet.json!')
