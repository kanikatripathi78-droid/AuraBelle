from flask import Flask, render_template, request, redirect, session, jsonify, Response
import sqlite3, random
from datetime import datetime
from functools import wraps
from pathlib import Path
import os
import shutil
import time
import tempfile
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'aurabelle_secret_key')


BASE_DIR = Path(__file__).resolve().parent
LEGACY_DB_PATH = BASE_DIR / "database.db"
DEFAULT_DB_DIR = Path(tempfile.gettempdir()) / "AuraBelle"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "database.db"
FALLBACK_DB_PATH = BASE_DIR / ".data" / "database.db"
TEMP_DB_PATH = Path(tempfile.gettempdir()) / "AuraBelle" / "database.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
DB_CONNECT_RETRIES = 3
DB_RETRY_DELAY_SECONDS = 0.35
ACTIVE_DB_PATH = None
SCHEMA_READY = False


def ensure_core_tables(conn):
    global SCHEMA_READY
    if SCHEMA_READY:
        return

    conn.executescript(
        '''
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
        );

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
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            product_id INTEGER,
            quantity INTEGER
        );

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
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            product_id INTEGER
        );
        '''
    )
    conn.commit()
    SCHEMA_READY = True


def prepare_database_path():
    global ACTIVE_DB_PATH
    if ACTIVE_DB_PATH is not None:
        return ACTIVE_DB_PATH

    candidate_paths = [DB_PATH, TEMP_DB_PATH, FALLBACK_DB_PATH]
    selected_path = None

    for candidate in candidate_paths:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if not candidate.exists() and LEGACY_DB_PATH.exists():
                try:
                    shutil.copy2(LEGACY_DB_PATH, candidate)
                except OSError:
                    # If copy fails, continue with fresh DB file.
                    pass

            # Validate this candidate can actually read/write.
            test_conn = sqlite3.connect(str(candidate), timeout=5)
            test_conn.execute("CREATE TABLE IF NOT EXISTS __db_healthcheck (id INTEGER)")
            test_conn.execute("INSERT INTO __db_healthcheck (id) VALUES (1)")
            test_conn.execute("DELETE FROM __db_healthcheck WHERE id=1")
            test_conn.commit()
            test_conn.close()
            selected_path = candidate
            break
        except (PermissionError, sqlite3.OperationalError, OSError):
            continue

    if selected_path is None:
        raise PermissionError("No writable database directory found.")

    ACTIVE_DB_PATH = selected_path
    return selected_path


# ===============================
# DATABASE CONNECTION
# ===============================
def get_db():
    db_file = prepare_database_path()
    last_error = None

    for attempt in range(DB_CONNECT_RETRIES):
        try:
            conn = sqlite3.connect(
                str(db_file),
                timeout=10,
                isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            ensure_core_tables(conn)
            return conn
        except sqlite3.OperationalError as err:
            last_error = err
            if attempt < DB_CONNECT_RETRIES - 1:
                time.sleep(DB_RETRY_DELAY_SECONDS * (attempt + 1))
                continue
            raise

    raise last_error


@app.errorhandler(sqlite3.OperationalError)
def handle_sqlite_operational_error(error):
    message = (
        "Database access issue detected. "
        "Please set DATABASE_PATH to a writable folder and restart the app."
    )
    return render_template(
        'login.html',
        db_error=message
    ), 500


def get_cart_count():
    if 'user' not in session:
        return 0

    conn = get_db()
    result = conn.execute(
        "SELECT SUM(quantity) as total FROM cart WHERE user_email=?",
        (session['user'],)
    ).fetchone()
    conn.close()

    return result['total'] or 0


def get_wishlist_count():
    if 'user' not in session:
        return 0

    conn = get_db()
    result = conn.execute(
        "SELECT COUNT(*) as total FROM wishlist WHERE user_email=?",
        (session['user'],)
    ).fetchone()
    conn.close()

    return result['total'] or 0


def ensure_extra_tables():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS product_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            product_id INTEGER,
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS product_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            product_id INTEGER,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_email, product_id)
        )
    ''')
    conn.execute('''
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            slug TEXT,
            description TEXT,
            image TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('''
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS newsletter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
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
    conn.commit()
    conn.close()


def ensure_social_tables():
    conn = get_db()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_email TEXT,
            following_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(follower_email, following_email)
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_email TEXT,
            receiver_email TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.commit()
    conn.close()


def ensure_product_columns():
    conn = get_db()
    columns = {
        row['name']
        for row in conn.execute("PRAGMA table_info(products)").fetchall()
    }

    if 'stock' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 20")
        conn.execute("UPDATE products SET stock = 20 WHERE stock IS NULL")
    if 'subcategory' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN subcategory TEXT DEFAULT ''")
    if 'original_price' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN original_price INTEGER DEFAULT 0")
    if 'images' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN images TEXT DEFAULT ''")
    if 'full_description' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN full_description TEXT DEFAULT ''")
    if 'sku' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN sku TEXT DEFAULT ''")
    if 'brand' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN brand TEXT DEFAULT ''")
    if 'is_featured' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN is_featured INTEGER DEFAULT 0")
    if 'is_new' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN is_new INTEGER DEFAULT 0")
    if 'is_sale' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN is_sale INTEGER DEFAULT 0")
    if 'discount_percent' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN discount_percent INTEGER DEFAULT 0")
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN created_at TIMESTAMP")
    if 'seller_email' not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN seller_email TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def ensure_order_columns():
    conn = get_db()
    columns = {
        row['name']
        for row in conn.execute("PRAGMA table_info(orders)").fetchall()
    }

    if 'tax' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN tax INTEGER DEFAULT 0")
    if 'name' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN name TEXT DEFAULT ''")
    if 'address' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN address TEXT DEFAULT ''")
    if 'city' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN city TEXT DEFAULT ''")
    if 'pincode' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN pincode TEXT DEFAULT ''")
    if 'phone' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN phone TEXT DEFAULT ''")
    if 'order_notes' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN order_notes TEXT DEFAULT ''")
    if 'grand_total' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN grand_total INTEGER DEFAULT 0")
        conn.execute("UPDATE orders SET grand_total = COALESCE(total, 0) WHERE grand_total IS NULL OR grand_total = 0")
    if 'payment_method' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'cod'")
    if 'payment_status' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'Pending'")
    if 'status' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Order Placed'")
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN created_at TIMESTAMP")
        conn.execute("UPDATE orders SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    conn.commit()
    conn.close()


def ensure_user_columns():
    conn = get_db()
    columns = {
        row['name']
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    if 'address' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN address TEXT DEFAULT ''")
    if 'city' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN city TEXT DEFAULT ''")
    if 'pincode' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN pincode TEXT DEFAULT ''")
    if 'profile_image' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN profile_image TEXT DEFAULT ''")
    if 'role' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    if 'is_active' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")

    conn.commit()
    conn.close()


def generate_order_id():
    ensure_order_columns()
    conn = get_db()

    while True:
        order_id = "AB" + datetime.now().strftime("%Y%m%d") + str(random.randint(1000, 9999))
        existing = conn.execute(
            "SELECT id FROM orders WHERE order_id=?",
            (order_id,)
        ).fetchone()

        if not existing:
            conn.close()
            return order_id


def simple_pdf(title, lines):
    escaped_lines = []
    for line in lines:
        escaped = str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        escaped_lines.append(escaped)

    text_commands = ["BT", "/F1 12 Tf", "50 790 Td", f"({title}) Tj"]
    for line in escaped_lines:
        text_commands.append("0 -20 Td")
        text_commands.append(f"({line}) Tj")
    text_commands.append("ET")

    stream = "\n".join(text_commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_position = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode()

    return pdf


def get_rating_summary(product_id):
    ensure_extra_tables()
    conn = get_db()
    result = conn.execute(
        "SELECT AVG(rating) as average_rating, COUNT(*) as rating_count FROM product_ratings WHERE product_id=?",
        (product_id,)
    ).fetchone()
    conn.close()

    average = result['average_rating'] or 0
    return {
        "average_rating": round(average, 1),
        "rating_count": result['rating_count'] or 0
    }


def get_user_rating(product_id):
    if 'user' not in session:
        return 0

    ensure_extra_tables()
    conn = get_db()
    result = conn.execute(
        "SELECT rating FROM product_ratings WHERE user_email=? AND product_id=?",
        (session['user'], product_id)
    ).fetchone()
    conn.close()

    return result['rating'] if result else 0


def is_product_wishlisted(product_id):
    if 'user' not in session:
        return False

    conn = get_db()
    result = conn.execute(
        "SELECT id FROM wishlist WHERE user_email=? AND product_id=?",
        (session['user'], product_id)
    ).fetchone()
    conn.close()

    return result is not None


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        if session.get('role') != 'admin':
            return redirect('/')
        return view_func(*args, **kwargs)
    return wrapped_view


def seller_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        if session.get('role') != 'seller':
            return redirect('/')
        return view_func(*args, **kwargs)
    return wrapped_view


# ===============================
# GLOBAL CART COUNT
# ===============================
@app.context_processor
def cart_count():
    return dict(cart_count=get_cart_count(), wishlist_count=get_wishlist_count())


# ===============================
# HOME PAGE
# ===============================
@app.route('/')
def home():
    return render_template('index.html')


# ===============================
# CATEGORIES PAGE
# ===============================
@app.route('/categories')
def categories():
    return render_template('categories.html')


# ===============================
# PRODUCTS PAGE (BY CATEGORY)
# ===============================
@app.route('/products/<category>')
def products(category):
    ensure_product_columns()
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM products WHERE category=?",
        (category,)
    ).fetchall()
    conn.close()

    return render_template('products.html', items=items)


# ===============================
# PRODUCT DETAIL PAGE
# ===============================
@app.route('/product/<int:id>')
def product_detail(id):
    ensure_product_columns()
    ensure_extra_tables()
    ensure_social_tables()
    ensure_user_columns()
    conn = get_db()
    product = conn.execute(
        "SELECT * FROM products WHERE id=?",
        (id,)
    ).fetchone()
    reviews = conn.execute(
        "SELECT * FROM product_reviews WHERE product_id=? ORDER BY created_at DESC",
        (id,)
    ).fetchall()
    related_products = conn.execute(
        "SELECT * FROM products WHERE category=? AND id != ? LIMIT 4",
        (product['category'], id)
    ).fetchall() if product else []
    artisan = None
    if product and product['seller_email']:
        artisan = conn.execute(
            "SELECT name, username, email, role FROM users WHERE email=?",
            (product['seller_email'],)
        ).fetchone()
    conn.close()

    rating = get_rating_summary(id)

    return render_template(
        'product_detail.html',
        product=product,
        average_rating=rating['average_rating'],
        rating_count=rating['rating_count'],
        user_rating=get_user_rating(id),
        is_wishlisted=is_product_wishlisted(id),
        reviews=reviews,
        related_products=related_products,
        artisan=artisan
    )


# ===============================
# ADD TO CART
# ===============================
@app.route('/add_to_cart/<int:id>')
def add_to_cart(id):
    if 'user' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, redirect='/login'), 401
        return redirect('/login')

    ensure_product_columns()
    conn = get_db()
    product = conn.execute(
        "SELECT stock FROM products WHERE id=?",
        (id,)
    ).fetchone()

    if not product or product['stock'] <= 0:
        conn.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='Out of stock'), 400
        return redirect(f'/product/{id}')

    # Check if already exists
    existing = conn.execute(
        "SELECT * FROM cart WHERE user_email=? AND product_id=?",
        (session['user'], id)
    ).fetchone()

    if existing:
        if existing['quantity'] >= product['stock']:
            conn.close()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Only limited stock available'), 400
            return redirect('/cart')

        conn.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=?",
            (existing['id'],)
        )
    else:
        conn.execute(
            "INSERT INTO cart (user_email, product_id, quantity) VALUES (?, ?, 1)",
            (session['user'], id)
        )

    conn.commit()
    conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, cart_count=get_cart_count())

    return redirect('/cart')


@app.route('/cart_count')
def current_cart_count():
    return jsonify(cart_count=get_cart_count())


@app.route('/wishlist_count')
def current_wishlist_count():
    return jsonify(wishlist_count=get_wishlist_count())


# ===============================
# RATE PRODUCT
# ===============================
@app.route('/rate_product/<int:id>', methods=['POST'])
def rate_product(id):
    if 'user' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, redirect='/login'), 401
        return redirect('/login')

    rating = request.form.get('rating')

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0

    if rating < 1 or rating > 5:
        return redirect(f'/product/{id}')

    ensure_extra_tables()
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM product_ratings WHERE user_email=? AND product_id=?",
        (session['user'], id)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE product_ratings SET rating=? WHERE id=?",
            (rating, existing['id'])
        )
    else:
        conn.execute(
            "INSERT INTO product_ratings (user_email, product_id, rating) VALUES (?, ?, ?)",
            (session['user'], id, rating)
        )

    conn.commit()
    conn.close()

    summary = get_rating_summary(id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(
            success=True,
            user_rating=rating,
            average_rating=summary['average_rating'],
            rating_count=summary['rating_count']
        )

    return redirect(f'/product/{id}')


# ===============================
# ADD PRODUCT REVIEW
# ===============================
@app.route('/add_review/<int:id>', methods=['POST'])
def add_review(id):
    if 'user' not in session:
        return redirect('/login')

    review = (request.form.get('review') or '').strip()
    if not review:
        return redirect(f'/product/{id}')

    ensure_extra_tables()
    conn = get_db()
    conn.execute(
        "INSERT INTO product_reviews (user_email, product_id, review) VALUES (?, ?, ?)",
        (session['user'], id, review)
    )
    conn.commit()
    conn.close()

    return redirect(f'/product/{id}')


# ===============================
# CART PAGE
# ===============================
@app.route('/cart')
def cart():
    if 'user' not in session:
        return redirect('/login')

    ensure_product_columns()
    conn = get_db()

    items = conn.execute('''
        SELECT products.*, cart.id as cart_id, cart.quantity 
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_email=?
    ''', (session['user'],)).fetchall()

    total = sum(item['price'] * item['quantity'] for item in items)

    conn.close()

    return render_template('cart.html', items=items, total=total)


@app.route('/update_cart/<int:id>', methods=['POST'])
def update_cart(id):
    if 'user' not in session:
        return redirect('/login')

    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1

    ensure_product_columns()
    conn = get_db()
    cart_item = conn.execute(
        '''
        SELECT cart.id, cart.product_id, products.stock
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.id=? AND cart.user_email=?
        ''',
        (id, session['user'])
    ).fetchone()

    if cart_item:
        if quantity <= 0:
            conn.execute("DELETE FROM cart WHERE id=?", (id,))
        else:
            quantity = min(quantity, cart_item['stock'])
            conn.execute("UPDATE cart SET quantity=? WHERE id=?", (quantity, id))

    conn.commit()
    conn.close()

    return redirect('/cart')


# ===============================
# REMOVE FROM CART
# ===============================
@app.route('/remove_from_cart/<int:id>')
def remove_from_cart(id):
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    conn.execute(
        "DELETE FROM cart WHERE id=? AND user_email=?",
        (id, session['user'])
    )

    conn.commit()
    conn.close()

    return redirect('/cart')


# ===============================
# CHECKOUT PAGE
# ===============================
@app.route('/checkout')
def checkout():
    if 'user' not in session:
        return redirect('/login')

    ensure_product_columns()
    conn = get_db()

    items = conn.execute('''
        SELECT products.*, cart.id as cart_id, cart.quantity 
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_email=?
    ''', (session['user'],)).fetchall()

    total = sum(item['price'] * item['quantity'] for item in items)

    if not items:
        conn.close()
        return redirect('/cart')

    order_id = generate_order_id()

    session['order'] = {
        "id": order_id,
        "total": total
    }

    user = conn.execute("SELECT * FROM users WHERE email=?", (session['user'],)).fetchone()
    conn.close()

    return render_template('checkout.html', items=items, total=total, order_id=order_id, user=user)


# ===============================
# PLACE ORDER
# ===============================
@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user' not in session:
        return redirect('/login')

    ensure_order_columns()
    ensure_product_columns()
    order = session.get('order')
    
    if not order:
        return redirect('/cart')

    # Get form data
    name = request.form.get('name')
    address = request.form.get('address')
    city = request.form.get('city')
    pincode = request.form.get('pincode')
    phone = request.form.get('phone')
    payment = request.form.get('payment', 'cod')
    order_notes = request.form.get('order_notes', '')

    conn = get_db()
    items = conn.execute('''
        SELECT cart.id as cart_id, cart.product_id, cart.quantity, products.stock
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_email=?
    ''', (session['user'],)).fetchall()

    if not items:
        conn.close()
        return redirect('/cart')

    for item in items:
        if item['quantity'] > item['stock']:
            conn.close()
            return redirect('/cart')

    # Calculate total with tax
    total_with_tax = order['total'] + (order['total'] * 0.18)
    
    # Determine payment status
    payment_status = "Pending" if payment == "cod" else "Paid"
    order_status = "Order Placed" if payment == "cod" else "Payment Received"

    conn.execute(
        "INSERT INTO orders (order_id, user_email, name, address, city, pincode, phone, total, tax, grand_total, payment_method, payment_status, status, order_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (order['id'], session['user'], name, address, city, pincode, phone, order['total'], order['total'] * 0.18, total_with_tax, payment, payment_status, order_status, order_notes)
    )

    # Save order items with product details
    for item in items:
        product = conn.execute("SELECT * FROM products WHERE id=?", (item['product_id'],)).fetchone()
        item_total = product['price'] * item['quantity']
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, product_name, price, quantity, total) VALUES (?, ?, ?, ?, ?, ?)",
            (order['id'], item['product_id'], product['name'], product['price'], item['quantity'], item_total)
        )

        conn.execute(
            "UPDATE products SET stock = CASE WHEN stock >= ? THEN stock - ? ELSE 0 END WHERE id=?",
            (item['quantity'], item['quantity'], item['product_id'])
        )

    # Clear cart
    conn.execute(
        "DELETE FROM cart WHERE user_email=?",
        (session['user'],)
    )

    conn.commit()
    conn.close()

    # Clear order from session
    session.pop('order', None)

    return redirect('/orders')


# ===============================
# ORDER HISTORY
# ===============================
@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect('/login')

    ensure_order_columns()
    ensure_extra_tables()
    conn = get_db()

    orders = conn.execute(
        "SELECT * FROM orders WHERE user_email=? ORDER BY created_at DESC, id DESC",
        (session['user'],)
    ).fetchall()

    # Fetch order items for each order
    orders_with_items = []
    for order in orders:
        order_dict = dict(order)
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id=?",
            (order['order_id'],)
        ).fetchall()
        order_dict['items'] = [dict(item) for item in items]
        orders_with_items.append(order_dict)

    conn.close()

    return render_template('orders.html', orders=orders_with_items)


@app.route('/cancel_order/<order_id>', methods=['POST'])
def cancel_order(order_id):
    if 'user' not in session:
        return redirect('/login')

    ensure_order_columns()
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=? AND user_email=?",
        (order_id, session['user'])
    ).fetchone()

    if order and order['status'] in ('Order Placed', 'Payment Received', 'Processing'):
        conn.execute(
            "UPDATE orders SET status='Cancelled', payment_status=? WHERE id=?",
            ('Refund Pending' if order['payment_status'] == 'Paid' else 'Cancelled', order['id'])
        )

    conn.commit()
    conn.close()

    return redirect('/orders')


# ===============================
# TRACK ORDER
# ===============================
@app.route('/track/<order_id>')
def track(order_id):
    conn = get_db()

    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=?",
        (order_id,)
    ).fetchone()

    conn.close()

    return render_template('track.html', order=order)


# ===============================
# INVOICE PAGE
# ===============================
@app.route('/invoice/<order_id>')
def invoice(order_id):
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=? AND user_email=?",
        (order_id, session['user'])
    ).fetchone()

    if not order:
        conn.close()
        return redirect('/orders')

    # Fetch order items
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?",
        (order_id,)
    ).fetchall()

    conn.close()

    return render_template('invoice.html', order=order, items=items)


@app.route('/invoice_pdf/<order_id>')
def invoice_pdf(order_id):
    if 'user' not in session:
        return redirect('/login')

    ensure_order_columns()
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=? AND user_email=?",
        (order_id, session['user'])
    ).fetchone()

    if not order:
        conn.close()
        return redirect('/orders')

    # Fetch order items
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?",
        (order_id,)
    ).fetchall()

    conn.close()

    lines = [
        "AuraBelle - Crafted by Hands, Cherished by Hearts",
        f"Bill ID: {order['order_id']}",
        f"Date: {order['created_at']}",
        f"Customer: {order['name']} ({order['user_email']})",
        f"Phone: {order['phone']}",
        f"Address: {order['address']}, {order['city']} - {order['pincode']}",
        "",
        "--- Ordered Products ---",
    ]

    for item in items:
        lines.append(f"{item['product_name']} x {item['quantity']} = Rs. {item['total']}")

    lines.extend([
        "",
        f"Subtotal: Rs. {order['total']}",
        f"Tax: Rs. {order['tax']}",
        "Shipping: Rs. 0",
        f"Grand Total: Rs. {order['grand_total']}",
        f"Payment: {order['payment_method'].upper()} - {order['payment_status']}",
        f"Status: {order['status']}",
        "Thank you for shopping with AuraBelle!",
    ])
    pdf = simple_pdf("AuraBelle Invoice", lines)

    return Response(
        pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=invoice_{order_id}.pdf'}
    )


# ===============================
# LOGIN
# ===============================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        ensure_user_columns()
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND is_active=1",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = email
            session['role'] = user['role'] if 'role' in user.keys() else 'user'
            if session['role'] == 'admin':
                return redirect('/admin')
            if session['role'] == 'seller':
                return redirect('/seller')
            return redirect('/')
        else:
            return "Invalid Credentials"

    return render_template('login.html')


# ===============================
# SIGNUP
# ===============================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.form

        ensure_user_columns()
        conn = get_db()
        role = (data.get('role') or 'user').strip().lower()
        if role not in ('user', 'seller', 'admin'):
            role = 'user'
        try:
            conn.execute(
                "INSERT INTO users (name, username, email, phone, password, address, city, pincode, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data['name'], data['username'], data['email'], data['phone'], generate_password_hash(data['password']),
                 data.get('address', ''), data.get('city', ''), data.get('pincode', ''), role)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template(
                'signup.html',
                signup_error="Email or username already exists. Please use different details."
            )
        conn.close()

        session['user'] = data['email']
        session['role'] = role
        if role == 'admin':
            return redirect('/admin')
        if role == 'seller':
            return redirect('/seller')
        return redirect('/')

    return render_template('signup.html')


# ===============================
# PROFILE
# ===============================
@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect('/login')

    ensure_order_columns()
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (session['user'],)
    ).fetchone()

    wishlist_count = conn.execute(
        "SELECT COUNT(*) as total FROM wishlist WHERE user_email=?",
        (session['user'],)
    ).fetchone()['total']

    orders_summary = conn.execute(
        "SELECT COUNT(*) as orders_count, COALESCE(SUM(grand_total), 0) as total_spent FROM orders WHERE user_email=?",
        (session['user'],)
    ).fetchone()

    conn.close()

    return render_template(
        'profile.html',
        user=user,
        wishlist_count=wishlist_count,
        orders_count=orders_summary['orders_count'],
        total_spent=orders_summary['total_spent']
    )


# ===============================
# LOGOUT
# ===============================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ===============================
# CONTACT FORM
# ===============================
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        conn = get_db()
        conn.execute(
            "INSERT INTO contact_messages (name, email, phone, subject, message) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, subject, message)
        )
        conn.commit()
        conn.close()
        
        return render_template('index.html', contact_success=True)
    
    return render_template('index.html')


# ===============================
# WISHLIST PAGE
# ===============================
@app.route('/wishlist')
def wishlist():
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    items = conn.execute('''
        SELECT products.*, wishlist.id as wishlist_id
        FROM wishlist
        JOIN products ON wishlist.product_id = products.id
        WHERE wishlist.user_email=?
    ''', (session['user'],)).fetchall()

    conn.close()

    return render_template('wishlist.html', items=items)


# ===============================
# ADD TO WISHLIST
# ===============================
@app.route('/add_to_wishlist/<int:id>')
def add_to_wishlist(id):
    if 'user' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, redirect='/login'), 401
        return redirect('/login')

    conn = get_db()

    # Check if already exists
    existing = conn.execute(
        "SELECT * FROM wishlist WHERE user_email=? AND product_id=?",
        (session['user'], id)
    ).fetchone()

    if not existing:
        conn.execute(
            "INSERT INTO wishlist (user_email, product_id) VALUES (?, ?)",
            (session['user'], id)
        )
        conn.commit()

    conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, wishlisted=True, wishlist_count=get_wishlist_count())

    return redirect('/wishlist')


# ===============================
# REMOVE FROM WISHLIST
# ===============================
@app.route('/remove_from_wishlist/<int:id>')
def remove_from_wishlist(id):
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    conn.execute(
        "DELETE FROM wishlist WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/wishlist')


# ===============================
# ADMIN PANEL
# ===============================
@app.route('/admin')
@admin_required
def admin_dashboard():
    ensure_product_columns()
    ensure_order_columns()
    ensure_user_columns()

    conn = get_db()

    stats = {
        "products": conn.execute("SELECT COUNT(*) as total FROM products").fetchone()['total'],
        "users": conn.execute("SELECT COUNT(*) as total FROM users").fetchone()['total'],
        "orders": conn.execute("SELECT COUNT(*) as total FROM orders").fetchone()['total'],
        "revenue": conn.execute(
            "SELECT COALESCE(SUM(grand_total), 0) as total FROM orders WHERE status!='Cancelled'"
        ).fetchone()['total']
    }

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC LIMIT 25"
    ).fetchall()
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC, id DESC LIMIT 25"
    ).fetchall()
    users = conn.execute(
        "SELECT id, name, email, phone, role, is_active, created_at FROM users ORDER BY id DESC LIMIT 25"
    ).fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        products=products,
        orders=orders,
        users=users
    )


@app.route('/admin/products/add', methods=['POST'])
@admin_required
def admin_add_product():
    ensure_product_columns()

    data = request.form
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    image = (data.get('image') or '').strip()

    if not name or not category:
        return redirect('/admin')

    try:
        price = int(data.get('price', 0))
    except ValueError:
        price = 0
    try:
        stock = int(data.get('stock', 0))
    except ValueError:
        stock = 0

    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, category, price, image, description, stock, original_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, category, max(price, 0), image, (data.get('description') or '').strip(), max(stock, 0), max(price, 0))
    )
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/admin/products/<int:product_id>/update', methods=['POST'])
@admin_required
def admin_update_product(product_id):
    ensure_product_columns()
    data = request.form

    try:
        price = int(data.get('price', 0))
    except ValueError:
        price = 0
    try:
        stock = int(data.get('stock', 0))
    except ValueError:
        stock = 0

    conn = get_db()
    conn.execute(
        '''
        UPDATE products
        SET name=?, category=?, price=?, stock=?, image=?, description=?, original_price=?
        WHERE id=?
        ''',
        (
            (data.get('name') or '').strip(),
            (data.get('category') or '').strip(),
            max(price, 0),
            max(stock, 0),
            (data.get('image') or '').strip(),
            (data.get('description') or '').strip(),
            max(price, 0),
            product_id
        )
    )
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/admin/orders/<order_id>/status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    ensure_order_columns()
    status = (request.form.get('status') or '').strip()
    valid_statuses = {'Order Placed', 'Processing', 'Shipped', 'Delivered', 'Cancelled'}
    if status not in valid_statuses:
        return redirect('/admin')

    conn = get_db()
    if status == 'Delivered':
        payment_status = 'Paid'
    elif status == 'Cancelled':
        payment_status = 'Refund Pending'
    else:
        payment_status = None

    if payment_status:
        conn.execute(
            "UPDATE orders SET status=?, payment_status=? WHERE order_id=?",
            (status, payment_status, order_id)
        )
    else:
        conn.execute(
            "UPDATE orders SET status=? WHERE order_id=?",
            (status, order_id)
        )
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_user_status(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT id, role, is_active FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if user and user['role'] != 'admin':
        new_status = 0 if user['is_active'] == 1 else 1
        conn.execute(
            "UPDATE users SET is_active=? WHERE id=?",
            (new_status, user_id)
        )

    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/seller')
@seller_required
def seller_dashboard():
    ensure_product_columns()
    conn = get_db()
    products = conn.execute(
        "SELECT * FROM products WHERE seller_email=? ORDER BY id DESC",
        (session['user'],)
    ).fetchall()
    conn.close()
    return render_template('seller_dashboard.html', products=products)


@app.route('/seller/products/add', methods=['POST'])
@seller_required
def seller_add_product():
    ensure_product_columns()
    data = request.form
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    if not name or not category:
        return redirect('/seller')

    try:
        price = int(data.get('price', 0))
    except ValueError:
        price = 0
    try:
        stock = int(data.get('stock', 0))
    except ValueError:
        stock = 0

    conn = get_db()
    conn.execute(
        """
        INSERT INTO products
        (name, category, price, image, description, stock, original_price, seller_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            category,
            max(price, 0),
            (data.get('image') or '').strip(),
            (data.get('description') or '').strip(),
            max(stock, 0),
            max(price, 0),
            session['user']
        )
    )
    conn.commit()
    conn.close()
    return redirect('/seller')


@app.route('/seller/products/<int:product_id>/update', methods=['POST'])
@seller_required
def seller_update_product(product_id):
    ensure_product_columns()
    data = request.form
    try:
        price = int(data.get('price', 0))
    except ValueError:
        price = 0
    try:
        stock = int(data.get('stock', 0))
    except ValueError:
        stock = 0

    conn = get_db()
    conn.execute(
        """
        UPDATE products
        SET name=?, category=?, price=?, stock=?, image=?, description=?, original_price=?
        WHERE id=? AND seller_email=?
        """,
        (
            (data.get('name') or '').strip(),
            (data.get('category') or '').strip(),
            max(price, 0),
            max(stock, 0),
            (data.get('image') or '').strip(),
            (data.get('description') or '').strip(),
            max(price, 0),
            product_id,
            session['user']
        )
    )
    conn.commit()
    conn.close()
    return redirect('/seller')


@app.route('/seller/products/<int:product_id>/delete', methods=['POST'])
@seller_required
def seller_delete_product(product_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM products WHERE id=? AND seller_email=?",
        (product_id, session['user'])
    )
    conn.commit()
    conn.close()
    return redirect('/seller')


@app.route('/artisan/<email>')
def artisan_profile(email):
    ensure_product_columns()
    ensure_user_columns()
    ensure_social_tables()
    conn = get_db()
    artisan = conn.execute(
        "SELECT id, name, username, email, role, profile_image FROM users WHERE email=?",
        (email,)
    ).fetchone()
    if not artisan:
        conn.close()
        return redirect('/')

    posted_products = conn.execute(
        "SELECT id, name, image, price FROM products WHERE seller_email=? ORDER BY id DESC",
        (email,)
    ).fetchall()
    products_count = len(posted_products)
    followers_count = conn.execute(
        "SELECT COUNT(*) as total FROM user_follows WHERE following_email=?",
        (email,)
    ).fetchone()['total']
    following_count = conn.execute(
        "SELECT COUNT(*) as total FROM user_follows WHERE follower_email=?",
        (email,)
    ).fetchone()['total']

    is_following = False
    if 'user' in session and session['user'] != email:
        rel = conn.execute(
            "SELECT id FROM user_follows WHERE follower_email=? AND following_email=?",
            (session['user'], email)
        ).fetchone()
        is_following = rel is not None

    conn.close()
    return render_template(
        'artisan_profile.html',
        artisan=artisan,
        products=posted_products,
        products_count=products_count,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following
    )


@app.route('/follow/<email>', methods=['POST'])
def toggle_follow(email):
    if 'user' not in session:
        return redirect('/login')
    if session['user'] == email:
        return redirect(f'/artisan/{email}')

    ensure_social_tables()
    conn = get_db()
    relation = conn.execute(
        "SELECT id FROM user_follows WHERE follower_email=? AND following_email=?",
        (session['user'], email)
    ).fetchone()
    if relation:
        conn.execute("DELETE FROM user_follows WHERE id=?", (relation['id'],))
    else:
        conn.execute(
            "INSERT OR IGNORE INTO user_follows (follower_email, following_email) VALUES (?, ?)",
            (session['user'], email)
        )
    conn.commit()
    conn.close()
    return redirect(f'/artisan/{email}')


@app.route('/dm/<email>', methods=['GET', 'POST'])
def dm_artisan(email):
    if 'user' not in session:
        return redirect('/login')
    if session['user'] == email:
        return redirect('/profile')

    ensure_social_tables()
    ensure_user_columns()
    conn = get_db()
    target_user = conn.execute(
        "SELECT name, username, email FROM users WHERE email=?",
        (email,)
    ).fetchone()
    if not target_user:
        conn.close()
        return redirect('/')

    if request.method == 'POST':
        text = (request.form.get('message') or '').strip()
        if text:
            conn.execute(
                "INSERT INTO direct_messages (sender_email, receiver_email, message) VALUES (?, ?, ?)",
                (session['user'], email, text)
            )
            conn.commit()

    messages = conn.execute(
        '''
        SELECT sender_email, receiver_email, message, created_at
        FROM direct_messages
        WHERE (sender_email=? AND receiver_email=?) OR (sender_email=? AND receiver_email=?)
        ORDER BY id ASC
        ''',
        (session['user'], email, email, session['user'])
    ).fetchall()
    conn.close()

    return render_template('dm_chat.html', target_user=target_user, messages=messages)


# ===============================
# RUN APP
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
