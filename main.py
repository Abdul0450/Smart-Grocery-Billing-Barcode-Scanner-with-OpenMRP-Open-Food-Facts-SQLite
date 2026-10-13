
import os
import time
import sqlite3
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import requests
from pyzbar.pyzbar import decode
from pydub import AudioSegment
from pydub.playback import play


# =========================================================
# 1. CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "grocery_store.db"
BEEP_FILE = BASE_DIR / "beep-02.wav"

OPENMRP_API_KEY = os.getenv("OPENMRP_API_KEY", "").strip()

OPENMRP_URL = "https://api.openmrp.in/v1/product/{}"
OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{}.json"

HEADERS = {
    "User-Agent": "SmartGroceryBilling/1.0 (personal project)"
}

if OPENMRP_API_KEY:
    HEADERS["x-api-key"] = OPENMRP_API_KEY

# Keep the existing six-column database structure.
conn = sqlite3.connect(str(DB_FILE))
conn.row_factory = sqlite3.Row

conn.execute("""
    CREATE TABLE IF NOT EXISTS products (
        barcode TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        brand TEXT DEFAULT '',
        unit TEXT DEFAULT '',
        price REAL,
        mrp REAL
    )
""")
conn.commit()


# =========================================================
# 2. BEEP SOUND
# =========================================================

try:
    beep_sound = AudioSegment.from_wav(str(BEEP_FILE))
except Exception:
    beep_sound = None
    print("Warning: beep-02.wav not found; sound disabled.")


def play_beep():
    if beep_sound is not None:
        try:
            threading.Thread(
                target=play,
                args=(beep_sound,),
                daemon=True
            ).start()
        except Exception as exc:
            print("Beep error:", exc)


# =========================================================
# 3. DATABASE LOOKUP
# =========================================================

def search_local_product(barcode):
    row = conn.execute("""
        SELECT barcode, product_name, brand, unit, price, mrp
        FROM products
        WHERE barcode = ?
    """, (barcode,)).fetchone()

    if not row:
        return None

    return {
        "barcode": row["barcode"],
        "name": row["product_name"] or "",
        "brand": row["brand"] or "",
        "unit": row["unit"] or "",
        "price": row["price"],
        "mrp": row["mrp"],
        "source": "Local SQLite database"
    }


# =========================================================
# 4. HELPER: NORMALIZE API RESPONSES
# =========================================================

def first_value(data, *keys):
    """Return the first non-empty value among possible API fields."""
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def normalize_product(data, barcode, source):
    """
    Accept several common product response shapes.
    API schemas may change, so inspect the raw response if
    a particular provider uses different field names.
    """
    if not isinstance(data, dict):
        return None

    # Handle common wrappers such as {"product": {...}}
    # and {"data": {"product": {...}}}.
    product = data

    for _ in range(3):
        nested = None

        for key in ("product", "data", "item", "result"):
            candidate = product.get(key)
            if isinstance(candidate, dict):
                nested = candidate
                break

        if nested is None:
            break

        product = nested

    name = first_value(
        product,
        "product_name",
        "product_name_en",
        "name",
        "title",
        "display_name"
    )

    brand = first_value(
        product, "brand", "brands", "brand_name"
    )

    unit = first_value(
        product,
        "quantity",
        "pack_size",
        "unit",
        "net_quantity",
        "size"
    )

    mrp = first_value(
        product,
        "mrp",
        "maximum_retail_price",
        "retail_price"
    )

    # Some APIs return nested price objects.
    if isinstance(mrp, dict):
        mrp = first_value(mrp, "amount", "value", "price")

    # Open Food Facts sometimes returns numeric pack quantity
    # separately from its unit.
    if not unit and product.get("product_quantity") is not None:
        quantity = product.get("product_quantity")
        quantity_unit = product.get("product_quantity_unit") or ""
        unit = f"{quantity} {quantity_unit}".strip()

    if isinstance(unit, dict):
        unit = first_value(unit, "label", "name", "value")

    # Convert prices safely.
    try:
        mrp = float(mrp) if mrp != "" else None
    except (TypeError, ValueError):
        mrp = None

    return {
        "barcode": str(
            first_value(product, "barcode", "code", "ean", "gtin")
            or barcode
        ),
        "name": str(name or ""),
        "brand": str(brand or ""),
        "unit": str(unit or ""),
        "price": None,
        "mrp": mrp,
        "categories": str(
            first_value(product, "categories", "category") or ""
        ),
        "image_url": str(
            first_value(product, "image_url", "image", "image_front_url")
            or ""
        ),
        "ingredients": str(
            first_value(product, "ingredients_text", "ingredients") or ""
        ),
        "source": source
    }


# =========================================================
# 5. SEARCH OPENMRP INDIA API
# =========================================================

def search_openmrp(barcode):
    if not OPENMRP_API_KEY:
        print("OpenMRP API key not configured; skipping OpenMRP.")
        return None

    url = OPENMRP_URL.format(barcode)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=12
        )

        if response.status_code == 404:
            print("Product not found in OpenMRP.")
            return None

        response.raise_for_status()
        data = response.json()

        print("OpenMRP response received.")

        product = normalize_product(
            data, barcode, "OpenMRP India"
        )

        if product and (
            product["name"]
            or product["brand"]
            or product["unit"]
            or product["mrp"] is not None
        ):
            return product

        print("OpenMRP response had no usable product details.")
        return None

    except requests.RequestException as exc:
        print("OpenMRP request error:", exc)
        return None

    except ValueError:
        print("OpenMRP returned invalid JSON.")
        return None


# =========================================================
# 6. SEARCH OPEN FOOD FACTS FALLBACK
# =========================================================

def search_open_food_facts(barcode):
    params = {
        "fields": (
            "code,product_name,product_name_en,brands,quantity,"
            "product_quantity,product_quantity_unit,categories,"
            "image_url,ingredients_text"
        )
    }

    try:
        response = requests.get(
            OFF_URL.format(barcode),
            params=params,
            headers=HEADERS,
            timeout=12
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != 1:
            print("Product not found in Open Food Facts.")
            return None

        product = normalize_product(
            data, barcode, "Open Food Facts"
        )

        if product and (
            product["name"]
            or product["brand"]
            or product["unit"]
        ):
            return product

        return None

    except (requests.RequestException, ValueError) as exc:
        print("Open Food Facts error:", exc)
        return None


# =========================================================
# 7. LOOKUP WORKFLOW
# =========================================================

def get_product(barcode):
    # Local data takes priority because it may contain
    # your corrected product details and store selling price.
    product = search_local_product(barcode)

    if product:
        return product

    print("Searching OpenMRP India...")
    product = search_openmrp(barcode)

    if product:
        return product

    print("Trying Open Food Facts...")
    product = search_open_food_facts(barcode)

    if product:
        return product

    return {
        "barcode": barcode,
        "name": "",
        "brand": "",
        "unit": "",
        "price": None,
        "mrp": None,
        "categories": "",
        "image_url": "",
        "ingredients": "",
        "source": "Manual entry - no API match"
    }


# =========================================================
# 8. EDIT AND SAVE PRODUCT FORM
# =========================================================

def edit_product(product):
    """
    Open an editable form. Saving inserts a new product
    or updates an existing record with the same barcode.
    """

    window = tk.Tk()
    window.title("Grocery Product Details - Edit and Save")
    window.geometry("620x680")
    window.minsize(560, 600)

    container = ttk.Frame(window, padding=18)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text="Product Information",
        font=("Arial", 17, "bold")
    ).pack(anchor="w", pady=(0, 5))

    ttk.Label(
        container,
        text=f"Data source: {product.get('source', 'Unknown')}",
        wraplength=560
    ).pack(anchor="w", pady=(0, 15))

    fields = [
        ("Barcode", "barcode", product.get("barcode", "")),
        ("Product name", "name", product.get("name", "")),
        ("Brand", "brand", product.get("brand", "")),
        ("Pack size / unit", "unit", product.get("unit", "")),
        ("MRP (Rs.)", "mrp", product.get("mrp")),
        ("Store selling price (Rs.)", "price", product.get("price")),
    ]

    entries = {}

    for label_text, key, value in fields:
        row = ttk.Frame(container)
        row.pack(fill="x", pady=5)

        ttk.Label(
            row,
            text=label_text,
            width=25
        ).pack(side="left", anchor="w")

        entry = ttk.Entry(row)
        entry.pack(side="left", fill="x", expand=True)

        if value is not None:
            entry.insert(0, str(value))

        if key == "barcode":
            entry.configure(state="readonly")

        entries[key] = entry

    # Additional API information is displayed but is not
    # stored in the six-column billing table.
    details = ttk.LabelFrame(
        container,
        text="Additional API Information",
        padding=10
    )
    details.pack(fill="x", pady=12)

    categories = tk.Text(details, height=2, wrap="word")
    categories.pack(fill="x", pady=3)
    categories.insert("1.0", product.get("categories", "") or "")
    categories.configure(state="disabled")

    ingredients = tk.Text(details, height=3, wrap="word")
    ingredients.pack(fill="x", pady=3)
    ingredients.insert("1.0", product.get("ingredients", "") or "")
    ingredients.configure(state="disabled")

    image_url = product.get("image_url", "") or ""

    ttk.Label(
        details,
        text=f"Image URL: {image_url or 'Not available'}",
        wraplength=550
    ).pack(anchor="w", pady=3)

    status = ttk.Label(
        container,
        text="Edit the details and click Save to Database.",
        wraplength=560
    )
    status.pack(anchor="w", pady=8)

    def save_product():
        barcode = entries["barcode"].get().strip()
        name = entries["name"].get().strip()
        brand = entries["brand"].get().strip()
        unit = entries["unit"].get().strip()

        if not barcode:
            messagebox.showerror("Error", "Barcode is required.")
            return

        if not name:
            messagebox.showerror(
                "Missing product name",
                "Enter the product name before saving."
            )
            return

        def parse_price(field_name):
            value = entries[field_name].get().strip()

            if not value:
                return None

            try:
                number = float(value)

                if number < 0:
                    raise ValueError

                return number

            except ValueError:
                raise ValueError(
                    f"{field_name.upper()} must be a valid "
                    "non-negative number or left blank."
                )

        try:
            mrp = parse_price("mrp")
            price = parse_price("price")
        except ValueError as exc:
            messagebox.showerror("Invalid price", str(exc))
            return

        if mrp is not None and price is not None and price > mrp:
            confirm = messagebox.askyesno(
                "Check prices",
                "The selling price is greater than the MRP. "
                "Save these values anyway?"
            )
            if not confirm:
                return

        try:
            conn.execute("""
                INSERT INTO products
                    (barcode, product_name, brand, unit, price, mrp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(barcode) DO UPDATE SET
                    product_name = excluded.product_name,
                    brand = excluded.brand,
                    unit = excluded.unit,
                    price = excluded.price,
                    mrp = excluded.mrp
            """, (
                barcode, name, brand, unit, price, mrp
            ))

            conn.commit()

            messagebox.showinfo(
                "Saved",
                f"{name} has been saved to your local database."
            )
            window.destroy()

        except sqlite3.Error as exc:
            conn.rollback()
            messagebox.showerror("Database error", str(exc))

    buttons = ttk.Frame(container)
    buttons.pack(fill="x", pady=12)

    ttk.Button(
        buttons,
        text="Save to Database",
        command=save_product
    ).pack(side="left", padx=(0, 10))

    ttk.Button(
        buttons,
        text="Cancel",
        command=window.destroy
    ).pack(side="left")

    window.mainloop()


# =========================================================
# 9. SHOW PRODUCT INFORMATION
# =========================================================

def show_product(barcode):
    print("\n" + "=" * 50)
    print("BARCODE:", barcode)

    product = get_product(barcode)

    print("Product name:", product.get("name") or "Not found")
    print("Brand:", product.get("brand") or "Not available")
    print("Pack size:", product.get("unit") or "Not available")
    print("MRP:", product.get("mrp") if product.get("mrp") is not None
          else "Not available")
    print("Store selling price:",
          product.get("price") if product.get("price") is not None
          else "Not set")
    print("Source:", product.get("source"))

    print("=" * 50)

    # Always open the form, including when no API match exists.
    # You can manually enter missing product details.
    edit_product(product)


# =========================================================
# 10. LIVE WEBCAM BARCODE SCANNER
# =========================================================

def main():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        conn.close()
        raise SystemExit(
            "Could not open webcam. Check the camera connection."
        )

    print("\nGrocery barcode scanner started.")
    print("Show a barcode to the webcam.")
    print("Press Q to quit.")

    # Avoid repeatedly opening the edit window while the same
    # barcode remains visible. It can be scanned again after
    # it disappears from the camera view.
    active_barcodes = set()
    last_scan_time = {}

    try:
        while True:
            success, frame = cap.read()

            if not success:
                print("Could not read webcam frame.")
                break

            frame = cv2.flip(frame, 1)
            decoded_barcodes = decode(frame)

            current_barcodes = set()

            for item in decoded_barcodes:
                barcode_number = item.data.decode(
                    "utf-8", errors="replace"
                ).strip()

                if not barcode_number:
                    continue

                current_barcodes.add(barcode_number)

                x, y, w, h = item.rect

                cv2.rectangle(
                    frame, (x, y), (x + w, y + h),
                    (0, 255, 0), 2
                )

                cv2.putText(
                    frame,
                    barcode_number,
                    (x, max(y - 10, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 255),
                    2
                )

                now = time.monotonic()

                if barcode_number in active_barcodes:
                    continue

                if now - last_scan_time.get(barcode_number, 0) < 2:
                    continue

                active_barcodes.add(barcode_number)
                last_scan_time[barcode_number] = now

                print("\nScanned successfully:", barcode_number)
                play_beep()

                # Stop the camera loop while the product form
                # is open; resume scanning when the form closes.
                show_product(barcode_number)

            # Release a barcode when it leaves the camera view.
            active_barcodes.intersection_update(current_barcodes)

            cv2.putText(
                frame,
                "Scan barcode | Q = Quit",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            cv2.imshow("Grocery Barcode Scanner", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        conn.close()
        print("\nScanner closed.")


if __name__ == "__main__":
    main()
