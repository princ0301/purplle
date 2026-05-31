import pandas as pd
import json
import uuid
import os
from datetime import datetime, timezone, timedelta


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def prepare_pos(csv_path: str, output_path: str):
    df = pd.read_csv(csv_path)

    orders = df.groupby('order_id').agg(
        store_id=('store_id', 'first'),
        order_date=('order_date', 'first'),
        order_time=('order_time', 'first'),
        total_amount=('total_amount', 'sum'),
        invoice_number=('invoice_number', 'first'),
    ).reset_index()

    def make_ts(row):
        d = datetime.strptime(row['order_date'] + ' ' + row['order_time'], '%d-%m-%Y %H:%M:%S')
        return d.strftime('%Y-%m-%dT%H:%M:%SZ')

    orders['timestamp'] = orders.apply(make_ts, axis=1)
    orders['transaction_id'] = orders['invoice_number']
    orders['basket_value_inr'] = orders['total_amount'].round(2)

    result = orders[['store_id', 'transaction_id', 'timestamp', 'basket_value_inr']]
    result.to_csv(output_path, index=False)
    print(f"POS: {len(result)} transactions written to {output_path}")
    return result


def prepare_store_layout(raw_csv_path: str, output_path: str):
    df = pd.read_csv(raw_csv_path)
    store_id = df['store_id'].iloc[0]
    store_name = df['store_name'].iloc[0]
    city = df['city'].iloc[0]

    layout = {
        "store_id": store_id,
        "store_name": store_name,
        "city": city,
        "address": "Brigade Road, Bangalore - 560025",
        "open_hours": {
            "monday":    {"open": "10:00", "close": "22:00"},
            "tuesday":   {"open": "10:00", "close": "22:00"},
            "wednesday": {"open": "10:00", "close": "22:00"},
            "thursday":  {"open": "10:00", "close": "22:00"},
            "friday":    {"open": "10:00", "close": "22:30"},
            "saturday":  {"open": "09:30", "close": "22:30"},
            "sunday":    {"open": "10:00", "close": "22:00"}
        },
        "cameras": [
            {"camera_id": "CAM_1", "label": "Main Floor - Skincare Wall", "type": "floor", "covers_zones": ["SKINCARE_WALL", "FLOOR_CENTER", "MAKEUP_TABLE"], "overlap_with": ["CAM_2"]},
            {"camera_id": "CAM_2", "label": "Entry / Exit Threshold", "type": "entry_exit", "covers_zones": ["ENTRY_ZONE", "FLOOR_CENTER"], "overlap_with": ["CAM_1"]},
            {"camera_id": "CAM_3", "label": "Back Wall", "type": "floor", "covers_zones": ["FACESHOP_ZONE", "GOODVIBES_ZONE", "DERMA_ZONE"], "overlap_with": ["CAM_1"]},
            {"camera_id": "CAM_4", "label": "Billing Counter", "type": "billing", "covers_zones": ["BILLING_ZONE", "CONSULTATION_AREA"], "overlap_with": []},
            {"camera_id": "CAM_5", "label": "Overhead Floor View", "type": "overhead", "covers_zones": ["FLOOR_CENTER", "ROTATING_STAND", "MAKEUP_TABLE"], "overlap_with": ["CAM_1", "CAM_3"]}
        ],
        "zones": [
            {"zone_id": "ENTRY_ZONE", "zone_name": "Entry / Exit", "sku_zone": None, "type": "entry_exit", "camera_ids": ["CAM_2"]},
            {"zone_id": "SKINCARE_WALL", "zone_name": "Skincare Wall", "sku_zone": "SKINCARE", "type": "product_zone", "camera_ids": ["CAM_1"]},
            {"zone_id": "FACESHOP_ZONE", "zone_name": "The Face Shop", "sku_zone": "FACE_CARE", "type": "product_zone", "camera_ids": ["CAM_1", "CAM_3"]},
            {"zone_id": "GOODVIBES_ZONE", "zone_name": "Good Vibes", "sku_zone": "NATURAL_CARE", "type": "product_zone", "camera_ids": ["CAM_3"]},
            {"zone_id": "DERMA_ZONE", "zone_name": "Derma & De-Tan", "sku_zone": "DERMA", "type": "product_zone", "camera_ids": ["CAM_3"]},
            {"zone_id": "MAKEUP_TABLE", "zone_name": "Makeup Display Table", "sku_zone": "MAKEUP", "type": "product_zone", "camera_ids": ["CAM_1", "CAM_5"]},
            {"zone_id": "ROTATING_STAND", "zone_name": "Rotating Product Stand", "sku_zone": "IMPULSE_BUY", "type": "product_zone", "camera_ids": ["CAM_1", "CAM_5"]},
            {"zone_id": "FLOOR_CENTER", "zone_name": "Main Floor Aisle", "sku_zone": None, "type": "transit_zone", "camera_ids": ["CAM_1", "CAM_2", "CAM_5"]},
            {"zone_id": "BILLING_ZONE", "zone_name": "Billing Counter", "sku_zone": None, "type": "billing", "camera_ids": ["CAM_4"]},
            {"zone_id": "CONSULTATION_AREA", "zone_name": "Beauty Consultation", "sku_zone": "PREMIUM", "type": "service_zone", "camera_ids": ["CAM_4"]}
        ],
        "staff_identifiers": {
            "method": "uniform_color",
            "description": "Store staff wear light grey or white uniform tops.",
            "hint_zones": ["BILLING_ZONE", "CONSULTATION_AREA"]
        }
    }

    with open(output_path, 'w') as f:
        json.dump(layout, f, indent=2)
    print(f"Layout: store_id={store_id}, written to {output_path}")
    return layout


def prepare_sample_events(store_id: str, output_path: str):
    zones = ["SKINCARE_WALL", "FACESHOP_ZONE", "GOODVIBES_ZONE", "DERMA_ZONE",
             "MAKEUP_TABLE", "ROTATING_STAND", "FLOOR_CENTER", "BILLING_ZONE"]

    camera_map = {
        "ENTRY_ZONE": "CAM_2", "SKINCARE_WALL": "CAM_1", "FACESHOP_ZONE": "CAM_1",
        "GOODVIBES_ZONE": "CAM_3", "DERMA_ZONE": "CAM_3", "MAKEUP_TABLE": "CAM_1",
        "ROTATING_STAND": "CAM_5", "FLOOR_CENTER": "CAM_5",
        "BILLING_ZONE": "CAM_4", "CONSULTATION_AREA": "CAM_4"
    }

    sku_map = {
        "SKINCARE_WALL": "SKINCARE", "FACESHOP_ZONE": "FACE_CARE",
        "GOODVIBES_ZONE": "NATURAL_CARE", "DERMA_ZONE": "DERMA",
        "MAKEUP_TABLE": "MAKEUP", "ROTATING_STAND": "IMPULSE_BUY",
        "FLOOR_CENTER": None, "BILLING_ZONE": None, "CONSULTATION_AREA": "PREMIUM"
    }

    import random
    base = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    events = []

    visitors = [{"visitor_id": "VIS_" + uuid.uuid4().hex[:6], "is_staff": i < 2} for i in range(15)]

    for idx, v in enumerate(visitors):
        vid = v["visitor_id"]
        is_staff = v["is_staff"]
        seq = 0
        ct = base + timedelta(seconds=idx * 30)

        def evt(event_type, zone_id=None, dwell_ms=0, queue_depth=None, cam=None):
            nonlocal seq
            camera = cam or camera_map.get(zone_id or "ENTRY_ZONE", "CAM_2")
            e = {
                "event_id": str(uuid.uuid4()),
                "store_id": store_id,
                "camera_id": camera,
                "visitor_id": vid,
                "event_type": event_type,
                "timestamp": ct.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "zone_id": zone_id,
                "dwell_ms": dwell_ms,
                "is_staff": is_staff,
                "confidence": round(random.uniform(0.80, 0.98), 2),
                "metadata": {"queue_depth": queue_depth, "sku_zone": sku_map.get(zone_id), "session_seq": seq}
            }
            seq += 1
            return e

        events.append(evt("ENTRY"))
        ct += timedelta(seconds=15)

        visit_zones = random.sample(zones, random.randint(2, 5))
        for zone in visit_zones:
            events.append(evt("ZONE_ENTER", zone_id=zone))
            ct += timedelta(seconds=random.randint(15, 40))
            dwell = random.randint(20, 120)
            ct += timedelta(seconds=dwell)
            if dwell >= 30:
                events.append(evt("ZONE_DWELL", zone_id=zone, dwell_ms=dwell * 1000))
                ct += timedelta(seconds=5)
            events.append(evt("ZONE_EXIT", zone_id=zone, dwell_ms=dwell * 1000))
            ct += timedelta(seconds=10)

            if zone == "BILLING_ZONE" and not is_staff:
                qd = random.randint(1, 4)
                events.append(evt("BILLING_QUEUE_JOIN", zone_id=zone, queue_depth=qd))
                ct += timedelta(seconds=20)
                if random.random() < 0.25:
                    events.append(evt("BILLING_QUEUE_ABANDON", zone_id=zone))
                    ct += timedelta(seconds=10)

        if idx in [3, 7] and not is_staff:
            events.append(evt("REENTRY"))
            ct += timedelta(seconds=10)

        events.append(evt("EXIT"))
        ct += timedelta(seconds=10)

        if len(events) >= 200:
            break

    events = events[:200]

    with open(output_path, 'w') as f:
        for e in events:
            f.write(json.dumps(e) + '\n')

    from collections import Counter
    types = Counter(e["event_type"] for e in events)
    print(f"Events: {len(events)} written to {output_path}")
    for k, v in sorted(types.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare dataset files from raw resources")
    parser.add_argument('--raw-csv', required=True, help='Path to raw POS CSV from Purplle')
    parser.add_argument('--data-dir', default=os.path.join(os.path.dirname(__file__), '..', 'data'), help='Output data directory')
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    
    print("=== Preparing dataset ===")

    pos_df = prepare_pos(
        csv_path=args.raw_csv,
        output_path=os.path.join(args.data_dir, 'pos_transactions.csv')
    )

    store_id = pos_df['store_id'].iloc[0]

    prepare_store_layout(
        raw_csv_path=args.raw_csv,
        output_path=os.path.join(args.data_dir, 'store_layout.json')
    )

    prepare_sample_events(
        store_id=store_id,
        output_path=os.path.join(args.data_dir, 'sample_events.jsonl')
    )

    print("\nDone. All dataset files ready in:", args.data_dir)