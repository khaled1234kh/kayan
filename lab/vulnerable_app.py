"""Intentionally vulnerable web application for pentesting lab.

This app contains common vulnerabilities for the pentesting agents to discover:
- SQL injection (login form)
- XSS (search/reflection)
- Command injection (ping utility)
- Directory traversal (file viewer)
- SSRF (URL fetcher)

WARNING: This app is intentionally vulnerable. Run ONLY in isolated lab environment.
"""

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import subprocess
import os
import httpx

app = FastAPI(title="KAYAN Lab — Vulnerable App")

# In-memory SQLite database
DB_PATH = "lab.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT
    )""")
    # Seed data
    c.execute("INSERT OR IGNORE INTO users (id, username, password, email, role) VALUES (1, 'admin', 'admin123', 'admin@lab.local', 'admin')")
    c.execute("INSERT OR IGNORE INTO users (id, username, password, email, role) VALUES (2, 'user1', 'password1', 'user1@lab.local', 'user')")
    c.execute("INSERT OR IGNORE INTO users (id, username, password, email, role) VALUES (3, 'user2', 'password2', 'user2@lab.local', 'user')")
    c.execute("INSERT OR IGNORE INTO products (id, name, price, description) VALUES (1, 'Widget A', 29.99, 'A great widget')")
    c.execute("INSERT OR IGNORE INTO products (id, name, price, description) VALUES (2, 'Widget B', 49.99, 'Another widget')")
    conn.commit()
    conn.close()

init_db()


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html><body>
    <h1>KAYAN Lab — Vulnerable App</h1>
    <ul>
        <li><a href="/login">Login (SQLi)</a></li>
        <li><a href="/search?q=test">Search (XSS)</a></li>
        <li><a href="/ping?host=127.0.0.1">Ping (Command Injection)</a></li>
        <li><a href="/file?path=README.md">File Viewer (Path Traversal)</a></li>
        <li><a href="/fetch?url=http://127.0.0.1:8000/health">URL Fetcher (SSRF)</a></li>
        <li><a href="/api/users">Users API</a></li>
        <li><a href="/api/products">Products API</a></li>
    </ul>
    </body></html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <html><body>
    <h1>Login</h1>
    <form method="POST" action="/login">
        <input name="username" placeholder="Username"><br>
        <input name="password" type="password" placeholder="Password"><br>
        <button type="submit">Login</button>
    </form>
    </body></html>
    """


@app.post("/login", response_class=HTMLResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    """VULNERABLE: SQL injection in username/password."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # INTENTIONALLY VULNERABLE: string concatenation
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    try:
        c.execute(query)
        user = c.fetchone()
        conn.close()
        if user:
            return f"<h1>Welcome, {user[1]}!</h1><p>Role: {user[5]}</p>"
        return "<h1>Login failed</h1>"
    except Exception as e:
        conn.close()
        return f"<h1>Error: {e}</h1>"


@app.get("/search", response_class=HTMLResponse)
async def search(q: str = Query(default="")):
    """VULNERABLE: Reflected XSS in search query."""
    # INTENTIONALLY VULNERABLE: no escaping
    return f"<html><body><h1>Search Results for: {q}</h1><p>No results found.</p></body></html>"


@app.get("/ping", response_class=HTMLResponse)
async def ping(host: str = Query(default="127.0.0.1")):
    """VULNERABLE: Command injection in host parameter."""
    try:
        # INTENTIONALLY VULNERABLE: shell=True with user input
        result = subprocess.run(f"ping -n 1 {host}", shell=True, capture_output=True, text=True, timeout=5)
        return f"<pre>{result.stdout}\n{result.stderr}</pre>"
    except Exception as e:
        return f"<pre>Error: {e}</pre>"


@app.get("/file", response_class=HTMLResponse)
async def file_viewer(path: str = Query(default="")):
    """VULNERABLE: Path traversal in file path."""
    try:
        # INTENTIONALLY VULNERABLE: no path sanitization
        with open(path, "r") as f:
            content = f.read()
        return f"<pre>{content}</pre>"
    except Exception as e:
        return f"<pre>Error: {e}</pre>"


@app.get("/fetch", response_class=HTMLResponse)
async def url_fetcher(url: str = Query(default="")):
    """VULNERABLE: SSRF in URL parameter."""
    try:
        # INTENTIONALLY VULNERABLE: fetches arbitrary URL
        resp = httpx.get(url, timeout=5.0)
        return f"<pre>{resp.text[:2000]}</pre>"
    except Exception as e:
        return f"<pre>Error: {e}</pre>"


@app.get("/api/users")
async def api_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users")
    users = [{"id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in c.fetchall()]
    conn.close()
    return JSONResponse(content=users)


@app.get("/api/products")
async def api_products():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price, description FROM products")
    products = [{"id": r[0], "name": r[1], "price": r[2], "description": r[3]} for r in c.fetchall()]
    conn.close()
    return JSONResponse(content=products)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
    print("Lab vulnerable app running on http://0.0.0.0:8888")
