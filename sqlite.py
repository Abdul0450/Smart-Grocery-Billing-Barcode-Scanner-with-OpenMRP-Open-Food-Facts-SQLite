import sqlite3

conn = sqlite3.connect("grocery_store.db")

barcode = "ENTER_ACTUAL_BARCODE"
product_name = "ENTER_PRODUCT_NAME"
brand = "ENTER_BRAND"
unit = "500 g"
price = 45.00
mrp = 50.00

conn.execute("""
INSERT OR REPLACE INTO products
(barcode, product_name, brand, unit, price, mrp)
VALUES (?, ?, ?, ?, ?, ?)
""", (
    barcode,
    product_name,
    brand,
    unit,
    price,
    mrp
))

conn.commit()
conn.close()

print("Product saved successfully.")