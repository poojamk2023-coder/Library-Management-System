from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import webbrowser
from datetime import datetime
from threading import Timer

app = Flask(__name__)
app.secret_key = "secure_production_level_key"

# =====================================================================
# FORCE PERMANENT DATABASE PATH DEFINITION (FIRES IN CURRENT PROJECT DIRECTORY)
# =====================================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(BASE_DIR, "library.db")

def get_db_connection():
    """Establishes a connection to the SQLite database file."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enables fetching columns by name like dictionary objects
    return conn

def init_db():
    """Creates tables and seeds mock user/book information only if completely empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Users Table Layout
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # 2. Create Unified Master Books Table Layout
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT NOT NULL,
            is_digital INTEGER NOT NULL,
            shelf_location TEXT,
            available_copies INTEGER,
            download_url TEXT,
            file_size_mb REAL
        )
    ''')

    # 3. Create Borrow Requests Queue Table Layout
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            book_id INTEGER NOT NULL,
            book_title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            request_date TEXT NOT NULL
        )
    ''')

    # Seed User Accounts Profile Array (Only if database table has 0 accounts)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?)", [
            ("admin@lib.com", "System Administrator", "admin123", "Admin"),
            ("librarian@lib.com", "Alice Smith (Staff)", "lib123", "Librarian"),
            ("student@edu.com", "John Doe (Student)", "user123", "Member")
        ])
        
    # Seed Starting Inventory (Only if database master catalog has 0 books total)
    cursor.execute("SELECT COUNT(*) FROM books")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO books (title, author, isbn, is_digital, shelf_location, available_copies) VALUES (?,?,?,?,?,?)",
                       ("Clean Code", "Robert C. Martin", "978-013", 0, "Aisle 4-B", 2))
        cursor.execute("INSERT INTO books (title, author, isbn, is_digital, download_url, file_size_mb) VALUES (?,?,?,?,?,?)",
                       ("Design Patterns", "Gang of Four", "978-020", 1, "https://example.com/patterns.pdf", 14.5))
        
    conn.commit()
    conn.close()

# Temporary runtime session system transaction audit logs
action_logs = ["Database Engine successfully mounted and listening via persistent disk."]

# =====================================================================
# SYSTEM LAYER WEB ROUTING CONTROLLERS
# =====================================================================

@app.route("/")
def index():
    """Renders the main layout application dashboard only if authenticated."""
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    books = conn.execute("SELECT * FROM books").fetchall()
    
    # Fetch all borrow requests to load onto the staff verification console view
    borrow_requests = conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    conn.close()
    
    return render_template(
        "index.html", 
        books=books, 
        requests=borrow_requests,
        current_user=session.get("user_name"),
        current_role=session.get("user_role"), 
        logs=action_logs
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles secure credentials verification profile lookups."""
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user and user["password"] == password:
            # Drop tracking attributes safely into browser session lockers
            session["user_email"] = user["email"]
            session["user_role"] = user["role"]
            session["user_name"] = user["name"]
            action_logs.append(f"[{user['role']}] {user['name']} logged in successfully.")
            return redirect(url_for("index"))
        
        flash("Invalid email or password parameter matching failed.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handles new user profile creation and database indexing."""
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
                (email, name, password, role)
            )
            conn.commit()
            action_logs.append(f"[System] Registered new profile: {name} as {role}")
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Error: An account with that email address already exists.", "danger")
        finally:
            conn.close()

    return render_template("register.html")

@app.route("/logout")
def logout():
    """Clears active session tracking state hashes entirely."""
    session.clear()
    return redirect(url_for("login"))

@app.route("/add-book", methods=["POST"])
def add_book():
    """Enforces active Guard Clause authentication verification for inventory management."""
    if "user_email" not in session:
        return redirect(url_for("login"))
        
    role = session.get("user_role")
    if role not in ["Admin", "Librarian"]:
        flash("CRITICAL: Access Denied! Account permission clearance layer validation failed.", "danger")
        return redirect(url_for("index"))

    title = request.form.get("title")
    author = request.form.get("author")
    isbn = request.form.get("isbn")
    book_type = request.form.get("book_type")
    
    conn = get_db_connection()
    if book_type == "physical":
        shelf = request.form.get("shelf_location")
        copies = request.form.get("copies")
        conn.execute("INSERT INTO books (title, author, isbn, is_digital, shelf_location, available_copies) VALUES (?,?,?,?,?,?)",
                     (title, author, isbn, 0, shelf, copies))
    else:
        url = request.form.get("download_url")
        size = request.form.get("file_size")
        conn.execute("INSERT INTO books (title, author, isbn, is_digital, download_url, file_size_mb) VALUES (?,?,?,?,?,?)",
                     (title, author, isbn, 1, url, size))
    
    conn.commit()
    conn.close()
    
    action_logs.append(f"[{role}] Saved record: '{title}' to persistent disk structures.")
    flash(f"Successfully added '{title}'!", "success")
    return redirect(url_for("index"))

@app.route("/action/<int:book_id>")
def handle_action(book_id):
    """Processes interactive item user interaction requests."""
    if "user_email" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    
    if not book:
        conn.close()
        flash("Target inventory asset footprint not found.", "danger")
        return redirect(url_for("index"))

    if book["is_digital"]:
        action_logs.append(f"[{session.get('user_role')}] Downloaded digital payload asset copy: '{book['title']}'")
        flash(f"Download link generated: {book['download_url']}", "info")
        conn.close()
    else:
        if book["available_copies"] > 0:
            already_requested = conn.execute(
                "SELECT * FROM requests WHERE user_email = ? AND book_id = ? AND status = 'Pending'",
                (session["user_email"], book_id)
            ).fetchone()

            if already_requested:
                flash("You already have an active pending borrow request loop open for this asset entry.", "warning")
            else:
                conn.execute(
                    "INSERT INTO requests (user_email, user_name, book_id, book_title, status, request_date) VALUES (?, ?, ?, ?, 'Pending', ?)",
                    (session["user_email"], session["user_name"], book_id, book["title"], datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                action_logs.append(f"[Member] {session['user_name']} submitted a borrow request tracking sequence for '{book['title']}'")
                flash(f"Borrow request for '{book['title']}' registered! Please present checkout context to desk staff for approval.", "success")
        else:
            flash(f"'{book['title']}' is currently out of stock on library floor.", "warning")
        conn.close()

    return redirect(url_for("index"))

@app.route("/approve-request/<int:request_id>")
def approve_request(request_id):
    """LIBRARIAN/ADMIN SEGMENT ACTION: Validates requests and deducts physical inventory units."""
    if "user_email" not in session or session.get("user_role") not in ["Admin", "Librarian"]:
        flash("Access Denied! Staff clearing requirements mismatch.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    req = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    
    if req:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (req["book_id"],)).fetchone()
        
        if book and book["available_copies"] > 0:
            conn.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (req["book_id"],))
            conn.execute("UPDATE requests SET status = 'Approved' WHERE id = ?", (request_id,))
            conn.commit()
            
            action_logs.append(f"[{session.get('user_role')}] Approved borrow request for {req['user_name']} -> '{req['book_title']}'")
            flash(f"Successfully checked out item to {req['user_name']} layout portfolio.", "success")
        else:
            flash("Action failed. The requested physical book configuration has dropped out of stock.", "danger")
    else:
        flash("Target operational queue tracking log item missing.", "danger")
        
    conn.close()
    return redirect(url_for("index"))

# =====================================================================
# STRICT ISOLATION MODULE: LIBRARIAN ROLE EXCLUSIVE RETURN CONTROLLER
# =====================================================================
@app.route("/return-book/<int:request_id>")
def return_book(request_id):
    """LIBRARIAN EXCLUSIVE ACTION: Marks books returned and replenishes stock fields."""
    # Enforces role isolation checkpoint: Admins are locked out from physical intake operations
    if "user_email" not in session or session.get("user_role") != "Librarian":
        flash("Access Denied! Only a designated Librarian can collect and confirm physical book returns.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    req = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    
    if req and req["status"] == "Approved":
        conn.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (req["book_id"],))
        conn.execute("UPDATE requests SET status = 'Returned' WHERE id = ?", (request_id,))
        conn.commit()
        
        action_logs.append(f"[Librarian] Confirmed physical Return intake from {req['user_name']} for '{req['book_title']}'")
        flash(f"Book return successfully logged by Librarian! Stock replenished.", "success")
    else:
        flash("Invalid transaction profile execution parameter matching failed.", "danger")
        
    conn.close()
    return redirect(url_for("index"))

# =====================================================================
# BROWSER AUTOMATION TARGET UTILITY
# =====================================================================
def launch_browser():
    """Triggers default browser window directly to the application link profile."""
    webbrowser.open_new_tab("http://127.0.0.1:5000/")

if __name__ == "__main__":
    init_db()  # Run check routines on sqlite schemas initialization
    
    # Wait exactly 1.5 seconds for Flask engine to fire up hooks, then launch browser tab
    Timer(1.5, launch_browser).start()
    
    # Boot server with reloader set to false to enforce exact singular tab launch sequence instances
    app.run(debug=True, use_reloader=False)