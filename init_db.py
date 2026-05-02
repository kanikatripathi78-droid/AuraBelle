import sqlite3
from pathlib import Path
import os
import shutil
import tempfile

# Resolve DB path (kept in LocalAppData by default to avoid OneDrive lock issues)
BASE_DIR = Path(__file__).resolve().parent
legacy_db_path = BASE_DIR / "database.db"
default_db_dir = Path(tempfile.gettempdir()) / "AuraBelle"
default_db_path = default_db_dir / "database.db"
fallback_db_path = BASE_DIR / ".data" / "database.db"
temp_db_path = Path(tempfile.gettempdir()) / "AuraBelle" / "database.db"
db_path = Path(os.getenv("DATABASE_PATH", str(default_db_path)))

for candidate in [db_path, temp_db_path, fallback_db_path]:
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if not candidate.exists() and legacy_db_path.exists():
            try:
                shutil.copy2(legacy_db_path, candidate)
            except OSError:
                pass

        test_conn = sqlite3.connect(str(candidate), timeout=5)
        test_conn.execute("CREATE TABLE IF NOT EXISTS __db_healthcheck (id INTEGER)")
        test_conn.execute("INSERT INTO __db_healthcheck (id) VALUES (1)")
        test_conn.execute("DELETE FROM __db_healthcheck WHERE id=1")
        test_conn.commit()
        test_conn.close()
        db_path = candidate
        break
    except (PermissionError, sqlite3.OperationalError, OSError):
        continue

# Connect DB
conn = sqlite3.connect(str(db_path), timeout=10)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL")
cursor.execute("PRAGMA synchronous=NORMAL")
cursor.execute("PRAGMA foreign_keys=ON")
cursor.execute("PRAGMA busy_timeout=10000")


# ===============================
# USERS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    phone TEXT,
    password TEXT,
    address TEXT,
    city TEXT,
    pincode TEXT,
    profile_image TEXT,
    role TEXT DEFAULT 'user',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# PRODUCTS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category TEXT,
    subcategory TEXT,
    price INTEGER,
    original_price INTEGER,
    image TEXT,
    images TEXT,
    description TEXT,
    full_description TEXT,
    stock INTEGER DEFAULT 20,
    sku TEXT,
    brand TEXT,
    is_featured INTEGER DEFAULT 0,
    is_new INTEGER DEFAULT 0,
    is_sale INTEGER DEFAULT 0,
    discount_percent INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# CART TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    product_id INTEGER,
    quantity INTEGER
)
''')


# ===============================
# ORDERS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    user_email TEXT,
    name TEXT,
    address TEXT,
    city TEXT,
    pincode TEXT,
    phone TEXT,
    total INTEGER,
    tax REAL,
    grand_total INTEGER,
    payment_method TEXT,
    payment_status TEXT,
    status TEXT,
    order_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# WISHLIST TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    product_id INTEGER
)
''')


# ===============================
# PRODUCT RATINGS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS product_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    product_id INTEGER,
    rating INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_email, product_id)
)
''')


# ===============================
# PRODUCT REVIEWS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS product_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    product_id INTEGER,
    review TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# ORDER ITEMS TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    product_id INTEGER,
    product_name TEXT,
    price INTEGER,
    quantity INTEGER,
    total INTEGER
)
''')


# ===============================
# CATEGORIES TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    slug TEXT,
    description TEXT,
    image TEXT,
    is_active INTEGER DEFAULT 1
)
''')


# ===============================
# CONTACT MESSAGES TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    subject TEXT,
    message TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# NEWSLETTER TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS newsletter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# USER ADDRESSES TABLE
# ===============================
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    name TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    pincode TEXT,
    phone TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')


# ===============================
# INSERT SAMPLE PRODUCTS
# ===============================

products = [
    # Card Making
    ("Floral Greeting Card", "cardmaking", 299, "https://images.unsplash.com/photo-1513201099705-a9746e1e201f?w=400", "Handmade floral card"),
    ("Birthday Celebration Card", "cardmaking", 349, "https://images.unsplash.com/photo-1513201099705-a9746e1e201f?w=400", "Beautiful birthday card"),
    ("Wedding Invitation Card", "cardmaking", 499, "https://images.unsplash.com/photo-1513201099705-a9746e1e201f?w=400", "Elegant wedding card"),
    
    # Scrapbooking
    ("Vintage Scrapbook", "scrapbooking", 499, "https://images.unsplash.com/photo-1544816155-12df9643f363?w=400", "Creative scrapbook design"),
    ("Travel Memory Book", "scrapbooking", 599, "https://images.unsplash.com/photo-1544816155-12df9643f363?w=400", "Travel memories album"),
    ("Family Photo Album", "scrapbooking", 699, "https://images.unsplash.com/photo-1544816155-12df9643f363?w=400", "Family moments album"),
    
    # Sewing
    ("Handmade Table Runner", "sewing", 450, "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400", "Decorative table runner"),
    ("Fabric Cushion Cover", "sewing", 350, "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400", "Hand-stitched cushion"),
    ("Quilted Pillowcase", "sewing", 400, "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400", "Soft pillowcase"),
    
    # Embroidery
    ("Embroidered Cushion", "embroidery", 799, "https://images.unsplash.com/photo-1558171813-4c088753af8f?w=400", "Hand embroidery cushion"),
    ("Floral Embroidery Art", "embroidery", 999, "https://images.unsplash.com/photo-1558171813-4c088753af8f?w=400", "Beautiful floral work"),
    ("Traditional Embroidery", "embroidery", 850, "https://images.unsplash.com/photo-1558171813-4c088753af8f?w=400", "Classic embroidery"),
    
    # Knitting
    ("Knitted Wool Scarf", "knitting", 699, "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?w=400", "Warm wool scarf"),
    ("Cozy Knitted Sweater", "knitting", 1299, "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?w=400", "Hand-knitted sweater"),
    ("Knitted Baby Blanket", "knitting", 899, "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?w=400", "Soft baby blanket"),
    
    # Crochetting
    ("Crochet Bag", "crochetting", 550, "https://images.unsplash.com/photo-1590874103328-eac38a5ade98?w=400", "Stylish crochet bag"),
    ("Crochet Doily", "crochetting", 350, "https://images.unsplash.com/photo-1590874103328-eac38a5ade98?w=400", "Decorative doily"),
    ("Crochet Tablemat", "crochetting", 450, "https://images.unsplash.com/photo-1590874103328-eac38a5ade98?w=400", "Elegant tablemat"),
    
    # Weaving
    ("Woven Wall Art", "weaving", 750, "https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=400", "Artistic wall hanging"),
    ("Handwoven Rug", "weaving", 1500, "https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=400", "Traditional rug"),
    ("Woven Tapestry", "weaving", 950, "https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=400", "Beautiful tapestry"),
    
    # Quilting
    ("Quilt Blanket", "quilting", 1200, "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400", "Soft quilt blanket"),
    ("Decorative Quilt", "quilting", 1800, "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400", "Handmade quilt"),
    ("Baby Quilt Set", "quilting", 900, "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=400", "Cute baby quilt"),
    
    # Pottery
    ("Clay Pot Vase", "pottery", 599, "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?w=400", "Decorative clay vase"),
    ("Handmade Ceramic Bowl", "pottery", 450, "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?w=400", "Ceramic bowl"),
    ("Terracotta Plant Pot", "pottery", 350, "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?w=400", "Plant pot"),
    
    # Sculpting with Clay
    ("Clay Sculpture", "sculpting", 1200, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Handmade sculpture"),
    ("Clay Figurine", "sculpting", 800, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Decorative figurine"),
    ("Clay Art Piece", "sculpting", 1500, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Artistic clay work"),
    
    # Porcelain Painting
    ("Porcelain Vase", "porcelain", 950, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Painted porcelain vase"),
    ("Porcelain Plate", "porcelain", 650, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Decorative plate"),
    ("Porcelain Tea Set", "porcelain", 1200, "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=400", "Tea set"),
    
    # Stained Glass Art
    ("Stained Glass Panel", "stainedglass", 1800, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Colorful glass panel"),
    ("Stained Glass Window", "stainedglass", 2500, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Decorative window"),
    ("Stained Glass Art", "stainedglass", 1500, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Glass art piece"),
    
    # Glass Blowing
    ("Blown Glass Vase", "glassblowing", 1100, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Hand-blown vase"),
    ("Glass Ornament", "glassblowing", 450, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Decorative ornament"),
    ("Blown Glass Bowl", "glassblowing", 750, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Glass bowl"),
    
    # Glass Painting
    ("Glass Painting Frame", "glasspainting", 650, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Colorful glass painting"),
    ("Decorative Glass Art", "glasspainting", 850, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Glass artwork"),
    ("Glass Painting Panel", "glasspainting", 750, "https://images.unsplash.com/photo-1513542789411-b6a0220ccb00?w=400", "Artistic panel"),
    
    # Jewellery Making
    ("Handmade Necklace", "jewellery", 899, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Elegant handmade jewellery"),
    ("Beaded Bracelet", "jewellery", 450, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Stylish bracelet"),
    ("Handcrafted Earrings", "jewellery", 550, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Beautiful earrings"),
    
    # Bead Stringing
    ("Beaded Necklace", "beadstringing", 650, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "String bead necklace"),
    ("Beaded Chain", "beadstringing", 450, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Decorative chain"),
    ("Beaded Jewelry Set", "beadstringing", 850, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Complete set"),
    
    # Bead Embroidery
    ("Embroidered Beadwork", "beadembroidery", 750, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Bead embroidery art"),
    ("Beaded Embroidery Piece", "beadembroidery", 950, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Handmade beadwork"),
    ("Decorative Bead Art", "beadembroidery", 850, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400", "Bead art piece"),
    
    # Acrylic Paintings
    ("Acrylic Landscape", "acrylic", 950, "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=400", "Acrylic landscape art"),
    ("Abstract Acrylic Art", "acrylic", 1200, "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=400", "Modern abstract"),
    ("Portrait Painting", "acrylic", 1500, "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=400", "Hand painted portrait"),
    
    # Mixed Media Crafts
    ("Mixed Media Canvas", "mixedmedia", 1100, "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=400", "Modern mixed media art"),
    ("Collage Artwork", "mixedmedia", 950, "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=400", "Creative collage"),
    ("Multi Media Piece", "mixedmedia", 1300, "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=400", "Artistic creation")
]

cursor.executemany('''
INSERT INTO products (name, category, price, image, description, stock, original_price, is_featured, is_new)
VALUES (?, ?, ?, ?, ?, 20, ?, 1, 1)
''', products)


# ===============================
# SAVE & CLOSE
# ===============================
conn.commit()
conn.close()

print("Database created & products inserted successfully ✅")
