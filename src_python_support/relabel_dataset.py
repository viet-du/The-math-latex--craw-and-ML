
import json
import re

# Đọc dữ liệu gốc
with open('datasheet.json', 'r', encoding='utf-8-sig') as f:
	data = json.load(f)

def relabel(item):
	desc = item.get('description', '').lower()
	label = item.get('label', '').lower()
	# Geometry
	if any(word in desc for word in ['area', 'perimeter', 'surface area', 'volume', 'circle', 'rectangle', 'polygon', 'cube', 'prism', 'tetrahedron', 'sphere', 'octagon', 'hexagon', 'trapezoid', 'ellipse', 'geometry']):
		return 'Geometry'
	# Calculus
	if any(word in desc for word in ['derivative', 'integral', 'differentiation', 'integration', 'riemann', 'simpson', 'limit', 'chain rule', 'product rule', 'quotient rule', 'fundamental theorem', 'leibniz', 'legendre', 'hypergeometric']):
		return 'Calculus'
	# Algebra
	if any(word in desc for word in ['arithmetic', 'geometric', 'sum', 'series', 'combination', 'permutation', 'polynomial', 'equation', 'algebra', 'pythagorean', 'identity']):
		return 'Algebra'
	# Trigonometry
	if any(word in desc for word in ['sine', 'cosine', 'tangent', 'cotangent', 'trigonometric', 'trigonometry', 'angle']):
		return 'Trigonometry'
	# Statistics
	if any(word in desc for word in ['probability', 'statistics', 'mean', 'variance', 'standard deviation', 'distribution']):
		return 'Statistics'
	# Nếu không khớp, giữ nguyên hoặc gán Other
	return 'Other'

# Gán lại label mới
data_new = []
for item in data:
	new_label = relabel(item)
	item['label_new'] = new_label
	data_new.append(item)

# Xuất ra file mới
with open('datasheet_relabel.json', 'w', encoding='utf-8') as f:
	json.dump(data_new, f, ensure_ascii=False, indent=2)

print('Đã tạo file datasheet_relabel.json với label mới (label_new)!')
