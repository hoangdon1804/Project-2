import sys
import os
from shapely.geometry import shape
from sqlalchemy.orm import Session

# Thêm đường dẫn để import được các module từ backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import SessionLocal, engine
from models import Zone, ZoneAdjacency, Base

def generate_adjacencies(district_id: int = None):
    db = SessionLocal()
    try:
        # 1. Lấy danh sách các Zone (có thể lọc theo District)
        query = db.query(Zone)
        if district_id:
            query = query.filter(Zone.district_id == district_id)
        zones = query.all()

        print(f"🔍 Đang xử lý {len(zones)} zones...")

        # 2. Xóa các quan hệ kề cũ để làm mới hoàn toàn
        # (Tùy chọn: Nếu bạn chỉ muốn cập nhật thêm thì bỏ dòng này)
        zone_ids = [z.id for z in zones]
        db.query(ZoneAdjacency).filter(
            ZoneAdjacency.zone_id1.in_(zone_ids)
        ).delete(synchronize_session=False)
        db.commit()

        adj_count = 0
        
        # 3. Chuyển đổi GeoJSON sang Shapely objects một lần để tối ưu
        zone_geoms = []
        for z in zones:
            if z.geometry:
                try:
                    # shape() chuyển đổi dict GeoJSON sang đối tượng Shapely
                    zone_geoms.append({
                        "id": z.id,
                        "name": z.name,
                        "poly": shape(z.geometry)
                    })
                except Exception as e:
                    print(f"⚠️ Lỗi định dạng hình học tại Zone {z.name}: {e}")

        # 4. So sánh từng cặp (Nested Loop - O(n^2))
        # Với số lượng phường trong 1 quận (~20-50), vòng lặp này chạy rất nhanh.
        for i in range(len(zone_geoms)):
            for j in range(i + 1, len(zone_geoms)):
                z1 = zone_geoms[i]
                z2 = zone_geoms[j]

                # Kiểm tra xem 2 đa giác có chạm nhau không
                # intersects() bao gồm cả việc chạm biên hoặc chồng lấn nhẹ
                # touches() chỉ tính chạm biên (đôi khi dữ liệu lỗi có khe hở nhỏ sẽ không nhận)
                if z1["poly"].intersects(z2["poly"]):
                    # Tạo quan hệ 2 chiều (z1 kề z2 và z2 kề z1)
                    adj1 = ZoneAdjacency(zone_id1=z1["id"], zone_id2=z2["id"], is_adjacent=True)
                    adj2 = ZoneAdjacency(zone_id1=z2["id"], zone_id2=z1["id"], is_adjacent=True)
                    
                    db.add(adj1)
                    db.add(adj2)
                    adj_count += 1
                    print(f" ✅ {z1['name']} <--> {z2['name']}")

        db.commit()
        print(f"\n🎉 HOÀN TẤT! Đã tạo {adj_count} cặp quan hệ kề nhau.")

    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Bạn có thể truyền ID của quận vào đây, hoặc để None để chạy toàn bộ
    # Ví dụ: generate_adjacencies(district_id=1)
    generate_adjacencies()