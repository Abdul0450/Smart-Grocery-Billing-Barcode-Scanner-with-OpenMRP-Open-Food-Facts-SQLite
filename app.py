import streamlit as st
import cv2
import numpy as np
import sqlite3
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. DATABASE SETUP (SQLite)
# ==========================================
DB_NAME = "indian_fmcg_products.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            brand TEXT,
            quantity TEXT,
            category TEXT,
            mrp REAL,
            source TEXT,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_product_from_db(barcode: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT barcode, product_name, brand, quantity, category, mrp, source, scanned_at 
        FROM products WHERE barcode = ?
    """, (barcode,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "barcode": row[0],
            "product_name": row[1],
            "brand": row[2],
            "quantity": row[3],
            "category": row[4],
            "mrp": row[5],
            "source": row[6],
            "scanned_at": row[7]
        }
    return None

def save_product_to_db(p: dict):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO products (barcode, product_name, brand, quantity, category, mrp, source, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p.get("barcode"),
        p.get("product_name", "Unknown Item"),
        p.get("brand", "N/A"),
        p.get("quantity", "N/A"),
        p.get("category", "General FMCG"),
        p.get("mrp", 0.0),
        p.get("source", "Open FMCG Database"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def get_all_products():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT barcode, product_name, brand, quantity, category, mrp, source, scanned_at 
        FROM products ORDER BY scanned_at DESC
    """, conn)
    conn.close()
    return df


# ==========================================
# 2. OPENCV BARCODE SCANNER
# ==========================================
def scan_barcode_with_opencv(image_bytes):
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return None, None

    detected_code = None
    annotated = image.copy()

    # 1. OpenCV Barcode Detector
    try:
        detector = cv2.barcode.BarcodeDetector()
        ok, decoded_info, _, points = detector.detectAndDecode(image)
        if ok and decoded_info:
            for info, pts in zip(decoded_info, points):
                if info:
                    detected_code = str(info).strip()
                    if pts is not None:
                        pts = pts.astype(int)
                        cv2.polylines(annotated, [pts], True, (0, 255, 0), 3)
                    break
    except Exception:
        pass

    # 2. Optional pyzbar fallback (great for 1D Indian EAN-13 barcodes)
    if not detected_code:
        try:
            from pyzbar.pyzbar import decode
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            barcodes = decode(gray)
            for b in barcodes:
                detected_code = b.data.decode("utf-8").strip()
                (x, y, w, h) = b.rect
                cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 3)
                break
        except Exception:
            pass

    annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
    return detected_code, annotated_rgb


# ==========================================
# 3. INDIAN FMCG EXTERNAL SEARCH
# ==========================================
def search_indian_fmcg(barcode: str):
    """
    Searches Indian FMCG / Grocery databases:
    1. Open Food Facts India (Groceries/Food)
    2. Open Beauty & Home Care Facts (Soaps, Detergents, Personal Care)
    """
    headers = {"User-Agent": "IndianGroceryScanner/2.0"}

    # List of open databases to check sequentially
    endpoints = [
        f"https://in.openfoodfacts.org/api/v2/product/{barcode}.json",
        f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
        f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json"
    ]

    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == 1:
                    p = data.get("product", {})

                    product_name = (
                        p.get("product_name_en")
                        or p.get("product_name")
                        or p.get("generic_name")
                        or f"Product {barcode}"
                    )
                    brand = p.get("brands") or "N/A"
                    quantity = p.get("quantity") or "N/A"
                    category = (
                        p.get("categories", "Grocery").split(",")[0]
                        if p.get("categories")
                        else "Grocery"
                    )

                    # Extract price/MRP if recorded in crowd-sourced fields
                    mrp = 0.0
                    if "price" in p:
                        try:
                            mrp = float(p.get("price"))
                        except (ValueError, TypeError):
                            mrp = 0.0

                    return {
                        "barcode": barcode,
                        "product_name": product_name,
                        "brand": brand,
                        "quantity": quantity,
                        "category": category,
                        "mrp": mrp,
                        "image_url": p.get("image_url", None),
                        "source": "Open FMCG Database (India)"
                    }
        except Exception:
            continue

    return None


# ==========================================
# 4. STREAMLIT APP
# ==========================================
def main():
    st.set_page_config(page_title="Indian FMCG Barcode Scanner", page_icon="🛒", layout="wide")
    init_db()

    st.title("🛒 Indian FMCG & Grocery Barcode Scanner")
    st.caption("Works with Indian EAN-13 barcodes (starting with 890). Searches local SQLite database, then queries open FMCG repositories.")

    col1, col2 = st.columns([1, 1])
    scanned_code = None

    with col1:
        st.subheader("📷 1. Scan Product Barcode")
        input_type = st.radio("Choose Input:", ["Webcam Snapshot", "Upload Image", "Type Barcode"], horizontal=True)

        if input_type == "Webcam Snapshot":
            cam = st.camera_input("Point camera at barcode and click 'Take Photo'")
            if cam:
                scanned_code, img_disp = scan_barcode_with_opencv(cam.getvalue())
                if img_disp is not None:
                    st.image(img_disp, caption="OpenCV Barcode Detection", use_container_width=True)

        elif input_type == "Upload Image":
            up = st.file_uploader("Upload product/barcode picture", type=["jpg", "jpeg", "png", "webp"])
            if up:
                scanned_code, img_disp = scan_barcode_with_opencv(up.getvalue())
                if img_disp is not None:
                    st.image(img_disp, caption="OpenCV Barcode Detection", use_container_width=True)

        elif input_type == "Type Barcode":
            manual = st.text_input("Enter Barcode (e.g., Maggi: 8901058852230):")
            if st.button("Search"):
                if manual.strip():
                    scanned_code = manual.strip()

    with col2:
        st.subheader("🔍 2. Product Details & MRP")

        if scanned_code:
            is_indian = scanned_code.startswith("890")
            st.info(f"🔢 **Barcode:** `{scanned_code}` " + ("*(Indian GS1 Barcode - 890)*" if is_indian else ""))

            # Step 1: Check SQLite
            db_item = get_product_from_db(scanned_code)

            if db_item:
                st.success("✅ **Found in Local SQLite Database!**")
                st.write(f"**Product:** {db_item['product_name']}")
                st.write(f"**Brand:** {db_item['brand']}")
                st.write(f"**Net Weight / Size:** {db_item['quantity']}")
                st.write(f"**Category:** {db_item['category']}")
                st.write(f"**Recorded MRP:** ₹ {db_item['mrp']:.2f}")
            else:
                st.warning("⚠️ Not in local SQLite. Searching external FMCG database...")

                with st.spinner("Fetching product details..."):
                    ext_item = search_indian_fmcg(scanned_code)

                if ext_item:
                    st.success("🎉 **Product details found! Saving to SQLite...**")
                    if ext_item.get("image_url"):
                        st.image(ext_item["image_url"], width=180)

                    st.write(f"**Product:** {ext_item['product_name']}")
                    st.write(f"**Brand:** {ext_item['brand']}")
                    st.write(f"**Quantity:** {ext_item['quantity']}")
                    st.write(f"**Category:** {ext_item['category']}")

                    # Save to DB
                    save_product_to_db(ext_item)
                    st.toast("Product added to SQLite database!", icon="💾")
                else:
                    st.error("❌ Product not found online. You can enter details manually:")
                    with st.form("manual_add"):
                        p_name = st.text_input("Product Name", "e.g., Parle-G Gold")
                        p_brand = st.text_input("Brand", "Parle")
                        p_qty = st.text_input("Pack Size", "100g")
                        p_cat = st.text_input("Category", "Biscuits")
                        p_mrp = st.number_input("Printed MRP (₹)", min_value=0.0, step=1.0)
                        if st.form_submit_button("Save to SQLite"):
                            save_product_to_db({
                                "barcode": scanned_code,
                                "product_name": p_name,
                                "brand": p_brand,
                                "quantity": p_qty,
                                "category": p_cat,
                                "mrp": p_mrp,
                                "source": "Manual Entry"
                            })
                            st.success("Saved!")
                            st.rerun()

    # Step 3: Stored Database Table
    st.markdown("---")
    st.subheader("📋 3. Stored Products Table (SQLite)")
    df = get_all_products()
    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "barcode": "Barcode",
                "product_name": "Product Name",
                "brand": "Brand",
                "quantity": "Pack Size",
                "category": "Category",
                "mrp": st.column_config.NumberColumn("MRP (₹)", format="₹ %.2f"),
                "source": "Source",
                "scanned_at": "Scanned Time"
            }
        )
    else:
        st.write("No items in database yet. Scan any product barcode above.")

if __name__ == "__main__":
    main()