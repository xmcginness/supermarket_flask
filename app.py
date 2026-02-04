from flask import Flask, render_template, request, redirect, session, flash
import csv
import os

app = Flask(__name__)
app.secret_key = "change-this-key"  # puedes poner cualquier texto

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_CSV = os.path.join(DATA_DIR, "users.csv")

def load_users():
    if not os.path.exists(USERS_CSV):
        return []
    with open(USERS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))

def user_exists(username):
    return any(u["username"] == username for u in load_users())

def add_customer(username, password):
    file_exists = os.path.exists(USERS_CSV)
    with open(USERS_CSV, "a", newline="", encoding="utf-8") as f:
        fieldnames = ["username", "password", "role"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")

        # Si el archivo está vacío, escribe cabecera
        if (not file_exists) or os.path.getsize(USERS_CSV) == 0:
            writer.writeheader()

        writer.writerow({"username": username, "password": password, "role": "customer"})

def check_login(username, password):
    for u in load_users():
        if u["username"] == username and u["password"] == password:
            return u
    return None

PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")

def load_products():
    if not os.path.exists(PRODUCTS_CSV):
        return []

    with open(PRODUCTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    # If CSV uses "Id", convert it into "id"
    for r in rows:
        if "id" not in r and "Id" in r:
            r["id"] = r["Id"]

    return rows


def save_products(products):
    with open(PRODUCTS_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "category", "name", "weight", "price", "status", "stock"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(products)

def get_product_by_id(product_id):
    for p in load_products():
        if str(p["id"]) == str(product_id):
            return p
    return None


@app.route("/")
def home():
    products = load_products()

    products_by_category = {}
    for p in products:
        cat = p.get("category", "Other")
        products_by_category.setdefault(cat, []).append(p)

    return render_template("home.html", products_by_category=products_by_category)

@app.route("/catalogue")
def catalogue():
    products = load_products()

    products_by_category = {}
    for p in products:
        cat = p.get("category", "Other")
        products_by_category.setdefault(cat, []).append(p)

    return render_template("catalogue.html", products_by_category=products_by_category)


@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please fill in both fields.")
            return redirect("/signup")

        if user_exists(username):
            flash("Username already taken.")
            return redirect("/signup")

        add_customer(username, password)
        flash("Signup successful. Please login.")
        return redirect("/login")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        u = check_login(username, password)
        if not u:
            flash("Wrong credentials.")
            return redirect("/login")

        session["user"] = u["username"]
        session["role"] = u["role"]
        flash(f"Logged in as {u['role']}.")
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect("/")

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})  # {"1": 2, "5": 1}
    items = []
    total = 0.0

    for pid, qty in cart_data.items():
        p = get_product_by_id(pid)
        if not p:
            continue

        price = float(p["price"])
        qty = int(qty)
        subtotal = price * qty
        total += subtotal

        items.append({
            "id": pid,
            "name": p["name"],
            "price": price,
            "qty": qty,
            "subtotal": subtotal
        })

    return render_template("cart.html", items=items, total=total)


@app.route("/add_to_cart/<product_id>", methods=["POST"])
def add_to_cart(product_id):
    p = get_product_by_id(product_id)
    if not p:
        flash("Product not found.")
        return redirect("/cart")


    stock = int(p["stock"])
    if stock <= 0:
        flash("Out of stock.")
        return redirect("/cart")


    cart_data = session.get("cart", {})
    current_qty = int(cart_data.get(str(product_id), 0))

    if current_qty + 1 > stock:
        flash("You cannot add more than available stock.")
        return redirect("/cart")


    cart_data[str(product_id)] = current_qty + 1
    session["cart"] = cart_data
    flash("Added to cart.")
    return redirect("/cart")



@app.route("/remove_from_cart/<product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart_data = session.get("cart", {})
    cart_data.pop(str(product_id), None)
    session["cart"] = cart_data
    flash("Removed from cart.")
    return redirect("/cart")


@app.route("/checkout", methods=["POST"])
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Cart is empty.")
        return redirect("/cart")

    products = load_products()

    # 1) Validate stock
    for pid, qty in cart_data.items():
        for p in products:
            if str(p["id"]) == str(pid):
                if int(p["stock"]) < int(qty):
                    flash(f"Not enough stock for {p['name']}.")
                    return redirect("/cart")

    # 2) Deduct stock + update status
    for pid, qty in cart_data.items():
        for p in products:
            if str(p["id"]) == str(pid):
                p["stock"] = str(int(p["stock"]) - int(qty))
                p["status"] = "Available" if int(p["stock"]) > 0 else "Out of stock"

    save_products(products)
    session["cart"] = {}
    flash("Payment successful!")
    return redirect("/")

def manager_required():
    return session.get("role") == "manager"


@app.route("/manager")
def manager():
    if not manager_required():
        flash("Manager access only.")
        return redirect("/login")

    products = load_products()
    return render_template("manager.html", products=products)


@app.route("/manager/add", methods=["GET", "POST"])
def manager_add():
    if not manager_required():
        flash("Manager access only.")
        return redirect("/login")

    if request.method == "POST":
        products = load_products()

        new_id = str(max([int(p["id"]) for p in products] + [0]) + 1)
        category = request.form.get("category", "").strip()
        name = request.form.get("name", "").strip()
        weight = request.form.get("weight", "").strip()
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()

        if not (category and name and weight and price and stock):
            flash("Fill all fields.")
            return redirect("/manager/add")

        try:
            stock_int = int(stock)
            float(price)
        except ValueError:
            flash("Price must be a number and stock must be an integer.")
            return redirect("/manager/add")

        status = "Available" if stock_int > 0 else "Out of stock"

        products.append({
            "id": new_id,
            "category": category,
            "name": name,
            "weight": weight,
            "price": price,
            "status": status,
            "stock": str(stock_int)
        })

        save_products(products)
        flash("Product added.")
        return redirect("/manager")

    return render_template("manager_add.html")


@app.route("/manager/edit/<product_id>", methods=["GET", "POST"])
def manager_edit(product_id):
    if not manager_required():
        flash("Manager access only.")
        return redirect("/login")

    products = load_products()
    product = next((p for p in products if str(p["id"]) == str(product_id)), None)

    if not product:
        flash("Product not found.")
        return redirect("/manager")

    if request.method == "POST":
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()

        if not price or not stock:
            flash("Fill all fields.")
            return redirect(f"/manager/edit/{product_id}")

        try:
            stock_int = int(stock)
            float(price)
        except ValueError:
            flash("Price must be a number and stock must be an integer.")
            return redirect(f"/manager/edit/{product_id}")

        product["price"] = price
        product["stock"] = str(stock_int)
        product["status"] = "Available" if stock_int > 0 else "Out of stock"

        save_products(products)
        flash("Product updated.")
        return redirect("/manager")

    return render_template("manager_edit.html", product=product)


@app.route("/manager/delete/<product_id>", methods=["POST"])
def manager_delete(product_id):
    if not manager_required():
        flash("Manager access only.")
        return redirect("/login")

    products = load_products()
    products = [p for p in products if str(p["id"]) != str(product_id)]
    save_products(products)

    flash("Product deleted.")
    return redirect("/manager")

@app.route("/ping")
def ping():
    return "PING OK"
@app.route("/routes")
def routes():
    return "<br>".join(sorted([str(r) for r in app.url_map.iter_rules()]))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(port=5001)

