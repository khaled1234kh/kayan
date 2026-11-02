"""Reset the lab environment to a known-vulnerable baseline state."""

import os
import sqlite3

DB_PATH = "lab.db"


def reset():
    """Delete and recreate the lab database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user'
    )""")
    c.execute("""CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT
    )""")
    c.execute("INSERT INTO users (id, username, password, email, role) VALUES (1, 'admin', 'admin123', 'admin@lab.local', 'admin')")
    c.execute("INSERT INTO users (id, username, password, email, role) VALUES (2, 'user1', 'password1', 'user1@lab.local', 'user')")
    c.execute("INSERT INTO users (id, username, password, email, role) VALUES (3, 'user2', 'password2', 'user2@lab.local', 'user')")
    c.execute("INSERT INTO products (id, name, price, description) VALUES (1, 'Widget A', 29.99, 'A great widget')")
    c.execute("INSERT INTO products (id, name, price, description) VALUES (2, 'Widget B', 49.99, 'Another widget')")
    conn.commit()
    conn.close()
    print("Lab database reset to baseline state.")


if __name__ == "__main__":
    reset()
