import json

def dedup_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"Tổng số bản ghi ban đầu: {len(data)}")

        seen_ids = set()
        deduped_data = []
        dup_count = 0
        dup_details = []

        for item in data:
            item_id = item.get('id')
            if item_id:
                if item_id in seen_ids:
                    dup_count += 1
                    dup_details.append(item_id)
                    continue
                seen_ids.add(item_id)
            
            # Giữ lại bản ghi nếu ID chưa tồn tại, hoặc nếu bản ghi không có trường 'id' (phòng trường hợp lỗi)
            deduped_data.append(item)

        print(f"Số bản ghi trùng lặp (bị loại bỏ): {dup_count}")
        if dup_details:
             print(f"Các ID bị trùng lặp: {set(dup_details)}")
        print(f"Số bản ghi còn lại: {len(deduped_data)}")

        # Lưu đè lại file
        with open(file_path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False để không bị hỏng font Tiếng Việt / LaTeX
            json.dump(deduped_data, f, ensure_ascii=False, indent=2)
            
        print(f"Hoàn tất lọc trùng. Dữ liệu đã được lưu lại vào {file_path}")

    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    # Đường dẫn tới file JSON cần lọc
    file_path = 'formulas/datasheet.json'
    dedup_json(file_path)
