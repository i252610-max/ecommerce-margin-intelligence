import sqlite3
import random
from datetime import datetime, timedelta
from faker import Faker

# ---- Reproducibility ----
random.seed(42)
Faker.seed(42)
fake = Faker()

# ---- Database connection ----
DB_PATH = "database/competitor_data.db"   # adjust if running from project root
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ========== DROP INTERNAL TABLES (but NEVER price_history) ==========
for table in ["internal_products", "internal_customers", "internal_orders"]:
    cursor.execute(f"DROP TABLE IF EXISTS {table}")

# ========== CREATE TABLES ==========
cursor.execute("""
CREATE TABLE internal_products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    cost REAL NOT NULL,
    selling_price REAL NOT NULL
)
""")

cursor.execute("""
CREATE TABLE internal_customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE internal_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES internal_customers(customer_id),
    FOREIGN KEY(product_id) REFERENCES internal_products(product_id)
)
""")

# ========== GENERATE PRODUCTS (~40 rows) ==========
products = []
categories = ["Fitness Apparel", "Fitness Apparel", "Fitness Apparel", "Desk Accessories"]  # weighted for 80% fitness

# We'll manually define some product names that are similar but not identical to scraped data
fitness_names = [
    "Power Training Tee", "Power T-Shirt Pro", "Power Performance Tee",
    "Arrival Contrast Tank", "Arrival Tank Top", "Crest Oversized Tee",
    "Crest T-Shirt Classic", "Geo Seamless T-Shirt", "Geo Seamless Top",
    "Shadow Seamless Tee", "Washed Pastels T-Shirt", "Washed Pastels Top",
    "Ribbed Tank 1PK", "Ribbed Tank 3 Pack", "Element Baselayer Tee",
    "Element Baselayer Top", "Critical Cut Off Tank", "Critical Drop Arm Tank",
    "Vital Seamless T-Shirt", "Vital Seamless Top", "Devant Seamless Tank",
    "Devant Seamless T-Shirt", "Train T-Shirt", "Train Cut Off Tank",
    "Running T-Shirt", "Running Elite Tank", "Distance Seamless T-Shirt",
    "Distance Seamless Tank", "Legacy T-Shirt", "Legacy Drop Arm Tank",
    "Power Cut Off Tank", "Power Stringer", "GSLC Stringer", "GSLC Cut Off Tank"
]
desk_names = [
    "Walnut Wood Keycap Set", "Walnut Wood Custom Keyboard Kit",
    "Retro Wireless Mechanical Keyboard", "Sofle Split Keyboard",
    "Magic Owl Keycaps Set", "Cthulhu Old God Keycap Set"
]

# Create 80% fitness, 20% desk
num_fitness = int(40 * 0.8)  # 32
num_desk = 40 - num_fitness     # 8

for i in range(num_fitness):
    pid = f"P{i+1:03d}"
    name = random.choice(fitness_names)
    category = "Fitness Apparel"
    # cost and selling price, with occasional bleeding
    cost = round(random.uniform(15, 50), 2)
    selling = round(cost * random.uniform(1.1, 2.0), 2)
    # Make some bleeders: 4-5 products where cost > selling
    if i < 5:  # first 5 are bleeders
        selling = round(cost * random.uniform(0.8, 0.95), 2)
    products.append((pid, name, category, cost, selling))

for i in range(num_desk):
    pid = f"P{num_fitness + i + 1:03d}"
    name = random.choice(desk_names)
    category = "Desk Accessories"
    cost = round(random.uniform(20, 300), 2)
    selling = round(cost * random.uniform(1.1, 2.5), 2)
    # maybe one bleeder
    if i == 0:
        selling = round(cost * 0.85, 2)
    products.append((pid, name, category, cost, selling))

cursor.executemany("""
INSERT INTO internal_products (product_id, product_name, category, cost, selling_price)
VALUES (?, ?, ?, ?, ?)
""", products)

# ========== GENERATE CUSTOMERS (~250 rows) ==========
customers = []
regions = ["North", "South", "East", "West"]
for i in range(250):
    cid = f"C{i+1:04d}"
    name = fake.name()
    email = fake.email()
    region = random.choice(regions)
    # signup_date within last 2 years
    signup = fake.date_between(start_date="-730d", end_date="-30d")
    customers.append((cid, name, email, region, signup.strftime("%Y-%m-%d")))

cursor.executemany("""
INSERT INTO internal_customers (customer_id, name, email, region, signup_date)
VALUES (?, ?, ?, ?, ?)
""", customers)


# ========== GENERATE ORDERS (~3,000 rows) ==========
# Global counter for unique sequential order IDs
order_counter = 0

def next_order_id():
    global order_counter
    order_counter += 1
    return f"O{order_counter:06d}"   # e.g., O000001, O000002, ...

# Assign personalities
personalities = ["Loyal", "Cooling", "Ghosted", "OneTimer"]
weights = [0.40, 0.25, 0.25, 0.10]
customer_personality = {}
for cid, *_ in customers:
    personality = random.choices(personalities, weights=weights, k=1)[0]
    customer_personality[cid] = personality

# Helper to generate order history for a customer
def generate_orders_for_customer(cid, personality):
    orders = []
    today = datetime.now().date()
    if personality == "Loyal":
        last_date = today - timedelta(days=random.randint(0, 30))
        interval_days = random.randint(14, 21)
        num_orders = random.randint(3, 6)
    elif personality == "Cooling":
        last_date = today - timedelta(days=random.randint(45, 75))
        interval_days = random.randint(21, 35)
        num_orders = random.randint(2, 4)
    elif personality == "Ghosted":
        last_date = today - timedelta(days=random.randint(100, 250))
        interval_days = random.randint(30, 60)
        num_orders = random.randint(1, 3)
    else:  # OneTimer
        last_date = today - timedelta(days=random.randint(200, 500))
        num_orders = 1
        interval_days = 0

    current_date = last_date
    for _ in range(num_orders):
        product = random.choice(products)
        quantity = random.randint(1, 3)
        unit_price = product[4]  # selling_price
        order_id = next_order_id()   # use sequential unique ID
        orders.append((order_id, cid, product[0], quantity, current_date.strftime("%Y-%m-%d"), unit_price))
        if interval_days > 0:
            current_date = current_date - timedelta(days=random.randint(interval_days-5, interval_days+5))
    return orders

all_orders = []
for cid, *rest in customers:
    personality = customer_personality[cid]
    orders = generate_orders_for_customer(cid, personality)
    all_orders.extend(orders)

# If total orders < 3000, add more from random customers
while len(all_orders) < 3000:
    cid = random.choice(customers)[0]
    product = random.choice(products)
    quantity = random.randint(1, 2)
    order_id = next_order_id()   # unique
    order_date = fake.date_between(start_date="-540d", end_date="-1d")
    all_orders.append((order_id, cid, product[0], quantity, order_date.strftime("%Y-%m-%d"), product[4]))

# Trim to exactly 3000 orders (IDs remain unique because they were assigned sequentially)
all_orders = all_orders[:3000]

cursor.executemany("""
INSERT INTO internal_orders (order_id, customer_id, product_id, quantity, order_date, unit_price)
VALUES (?, ?, ?, ?, ?, ?)
""", all_orders)

# ========== COMMIT & CLOSE ==========
conn.commit()
conn.close()

print(" Synthetic data generated and loaded into database.")