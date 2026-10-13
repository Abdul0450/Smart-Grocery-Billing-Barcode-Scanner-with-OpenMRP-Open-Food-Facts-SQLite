# Smart-Grocery-Billing-Barcode-Scanner-with-OpenMRP-Open-Food-Facts-SQLite

📌 Project Overview
Smart Grocery Billing is a Python-based grocery product lookup application that uses a live webcam to scan product barcodes and retrieve product information from online APIs. It prioritizes locally saved product details, searches OpenMRP India, and falls back to Open Food Facts when a product is not found.
The application provides an editable product form where users can enter or update product information and save it to a local SQLite database for future scans.
✨ Features
- Live Barcode Scanning: Scan product barcodes using a webcam.
- Local Database Lookup: Search previously saved products in SQLite.
- OpenMRP India API: Retrieve product information using a barcode and an API key.
- Open Food Facts API: Automatically search a secondary product database.
- Automatic Fallback: Open a manual-entry form when no online product match is found.
- Editable Product Details: Update product name, brand, pack size, MRP, and store selling price.
- Persistent Storage: Save product information locally for future use.
- Duplicate Prevention: Update existing products using their barcode instead of creating duplicate records.
- Scan Confirmation Sound: Play a beep sound after a successful barcode scan.
- Price Validation: Validate numeric prices and warn when the selling price exceeds the MRP.
- Additional Product Information: Display available categories, ingredients, and image URLs.
- Scan Debouncing: Reduce repeated scans while a barcode remains visible.
🛠️ Technologies Used
- Python
- OpenCV
- SQLite
- Tkinter
- Requests
- Pyzbar
- Pydub
- OpenMRP India API
- Open Food Facts API
🔄 How It Works
1. The webcam captures live video using OpenCV.
2. Pyzbar detects and decodes the product barcode.
3. The application searches the local SQLite database.
4. If the product is not found locally, it queries the OpenMRP India API.
5. If OpenMRP does not return a usable result, the application searches Open Food Facts.
6. If no product information is available, a manual-entry form opens.
7. The user reviews or edits the product details.
8. The product information is saved to the SQLite database.
9. On future scans, the application can retrieve the saved product details locally.
📂 Project Structure
Smart-Grocery-Billing/
│
├── main.py
├── beep-02.wav
├── grocery_store.db
├── requirements.txt
└── README.md


- main.py — Main application containing barcode scanning, API integration, database operations, and the Tkinter interface.
- beep-02.wav — Audio file played after a successful scan.
- grocery_store.db — SQLite database created automatically when the application runs.
- requirements.txt — Python dependencies.
- README.md — Project documentation.
Note: The database file is created automatically. You do not need to create it manually.
⚙️ Installation
1. Install Python
Install Python 3.10 or a compatible version from the official website:
https://www.python.org/downloads/
2. Clone the repository
git clone https://github.com/YOUR_USERNAME/Smart-Grocery-Billing.git
cd Smart-Grocery-Billing


Replace YOUR_USERNAME with your GitHub username.
3. Install dependencies
pip install opencv-python requests pyzbar pydub


Additional requirements:
- Install the ZBar library or runtime required by Pyzbar for your operating system.
- Install FFmpeg if your audio playback setup requires it.
- Tkinter is included with many standard Python installations, but some Linux installations require a separate Tkinter package.
4. Configure the OpenMRP API key
The OpenMRP API key is read from an environment variable rather than being hardcoded into the application.
Windows Command Prompt:
set OPENMRP_API_KEY=your_api_key_here


Windows PowerShell:
$env:OPENMRP_API_KEY="your_api_key_here"


Obtain your API key from the OpenMRP provider if API access is available to your account. Without the key, the application skips OpenMRP and continues to Open Food Facts.
Never commit your real API key to GitHub.
5. Add the beep sound
Place beep-02.wav in the same folder as main.py. If the file is missing or cannot be loaded, the application continues without sound.

▶️ Run the Application
Start the barcode scanner using:
python main.py


Then:
1. Allow the application to access your webcam.
2. Hold a product barcode in front of the camera.
3. Wait for the barcode to be detected.
4. Review the product details in the form.
5. Enter any missing information, especially the store selling price.
6. Click Save to Database.
7. Scan another product after the form closes.
8. Press Q in the scanner window to exit.
   
🗄️ Database Structure
The application creates a products table in grocery_store.db.
Column	Description
barcode	Unique product barcode and primary key
product_name	Name of the grocery product
brand	Product brand
unit	Pack size or quantity
price	Store selling price
mrp	Maximum retail price
The barcode is used as the primary key, allowing the application to update a product's details when the same barcode is saved again.

🌐 API Integration
OpenMRP India
- Used as the first online product lookup source.
- Requires an API key configured through OPENMRP_API_KEY.
- Product information depends on the provider's API response and database coverage.
Open Food Facts
- Used as a fallback product lookup source.
- Provides available product details such as name, brand, quantity, categories, ingredients, and images.
- Does not guarantee that every Indian grocery product will be available.
- Generally does not provide the local store's selling price.
API responses can vary, and product availability depends on the provider's database and API access.

💰 Product Pricing
This application distinguishes between:
- MRP: Maximum retail price retrieved from an API when available or entered manually.
- Store Selling Price: The price charged by the local grocery store.
The selling price should be reviewed and entered by the store operator when it is not available. The application does not automatically determine current market prices.

🔐 Security and Limitations
- Store API keys in environment variables.
- Do not upload API keys, passwords, or private credentials to GitHub.
- Online product information may be incomplete or inaccurate.
- Barcode scanning depends on camera quality, lighting, barcode condition, and focus.
- The current version stores product details but does not yet implement a complete shopping cart, quantity management, GST calculation, invoice generation, or checkout workflow.
- This is a desktop application designed for local use; it does not currently provide a multi-user or cloud-based database.
  
🚀 Future Improvements
- Add a shopping cart with quantity and subtotal calculations.
- Generate printable grocery bills and PDF invoices.
- Add GST and discount calculations.
- Create daily sales reports and inventory tracking.
- Add product images to the user interface.
- Support USB barcode scanners alongside webcam scanning.
- Add low-stock alerts and stock quantity management.
- Develop a more advanced billing dashboard.
- Support multiple stores and shared databases.
  
👨‍💻 Author
Abdul Samee Qureshi
Python Developer | Computer Vision Enthusiast | AI & Data Projects
📄 License
This project is intended for educational and personal development purposes. You may add an MIT License if you want to permit reuse, modification, and distribution under its terms.

Note: This version is a barcode-based product lookup and product database application. A full grocery billing system with cart management and invoice generation can be added as the next development stage.
