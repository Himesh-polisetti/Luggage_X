import streamlit as st
import sqlite3
from geopy.distance import geodesic
from datetime import date
import random

# ---------------- CONFIG ----------------
st.set_page_config(page_title="LuggageX", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT,
    location TEXT,
    phone TEXT)''')

# ✅ Added OTP column
c.execute('''CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    host TEXT,
    location TEXT,
    delivery TEXT,
    bags INTEGER,
    distance REAL,
    price REAL,
    status TEXT,
    payment_status TEXT,
    pickup_date TEXT,
    delivery_date TEXT,
    otp TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    given_by TEXT,
    given_to TEXT,
    rating INTEGER)''')

conn.commit()

# ---------------- FUNCTIONS ----------------
def get_rating(user):
    c.execute("SELECT AVG(rating) FROM ratings WHERE given_to=?", (user,))
    r = c.fetchone()[0]
    return round(r,2) if r else 3

# ✅ More cities added
city_coords = {
    "Visakhapatnam": (17.6868, 83.2185),
    "Vijayawada": (16.5062, 80.6480),
    "Guntur": (16.3067, 80.4365),
    "Tirupati": (13.6288, 79.4192),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Bangalore": (12.9716, 77.5946),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025)
}
cities = list(city_coords.keys())

def get_distance(c1, c2):
    return geodesic(city_coords[c1], city_coords[c2]).km

def price_calc(bags, dist):
    return bags*40 + dist*4

def generate_otp():
    return str(random.randint(1000,9999))

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN ----------------
if st.session_state.user is None:
    st.title("🎒 LuggageX")

    opt = st.radio("Login/Signup", ["Login","Signup"])
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if opt=="Signup":
        role = st.selectbox("Role", ["Customer","Host"])
        loc = st.selectbox("Location", cities)
        ph = st.text_input("Phone")

        if st.button("Signup"):
            try:
                c.execute("INSERT INTO users VALUES (?,?,?,?,?)",(u,p,role,loc,ph))
                conn.commit()
                st.success("Account created")
            except:
                st.error("User exists")

    if opt=="Login":
        role = st.selectbox("Role", ["Customer","Host"])
        if st.button("Login"):
            c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?",(u,p,role))
            res = c.fetchone()
            if res:
                st.session_state.user = res
                st.rerun()
            else:
                st.error("Invalid login")

# ---------------- MAIN ----------------
else:
    user, pw, role, loc, ph = st.session_state.user

    st.sidebar.write(f"{user} ({role})")
    page = st.sidebar.selectbox("Menu", ["Home","Dashboard","History","Help Line"])

    if st.sidebar.button("Logout"):
        st.session_state.user=None
        st.rerun()

    # ---------------- CUSTOMER ----------------
    if role=="Customer" and page=="Home":
        st.title("📦 Create Request")

        bags = st.number_input("Bags",1)
        pick = st.selectbox("Pickup Location", cities)
        drop = st.selectbox("Delivery Location", cities)

        pickup_date = st.date_input("Pickup Date", value=date.today())
        delivery_date = st.date_input("Delivery Date", value=date.today())

        dist = get_distance(pick, drop)
        price = price_calc(bags, dist)

        st.info(f"{dist:.2f} km | ₹{price:.2f}")

        if st.button("Pay & Request"):
            otp = generate_otp()

            c.execute('''INSERT INTO requests 
            VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (user,"",pick,drop,bags,dist,price,"Pending","Paid",
             str(pickup_date), str(delivery_date), otp))
            conn.commit()

            st.success(f"Order placed! 🔐 OTP: {otp}")

    # ---------------- HOST ----------------
    if role=="Host" and page=="Home":
        st.title("📦 Requests")

        c.execute("SELECT * FROM requests WHERE status='Pending' AND host=''")

        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp = r

            title = f"{loc1} → {loc2} | ₹{price} | 📅 {pdate}"
            st.info(title)

            col1, col2 = st.columns(2)

            with col1:
                if st.button(f"✅ Accept: {title}", key=f"a{rid}"):
                    c.execute("UPDATE requests SET host=?, status='Accepted' WHERE id=?", (user, rid))
                    conn.commit()
                    st.rerun()

            with col2:
                if st.button(f"❌ Reject: {title}", key=f"r{rid}"):
                    c.execute("UPDATE requests SET status='Rejected' WHERE id=?", (rid,))
                    conn.commit()
                    st.rerun()

        # ACTIVE JOBS
        c.execute('''SELECT r.*, u.phone FROM requests r
                     JOIN users u ON r.username=u.username
                     WHERE r.host=?''',(user,))

        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp, cust_phone = r

            if status=="Accepted":
                st.success(f"✅ {loc1} → {loc2} | 📞 {cust_phone}")

                if st.button(f"🚀 Start Trip ({pdate})", key=f"s{rid}"):
                    c.execute("UPDATE requests SET status='In Transit' WHERE id=?", (rid,))
                    conn.commit()
                    st.rerun()

            elif status=="In Transit":
                st.warning(f"🚚 Delivering: {loc1} → {loc2}")

                entered_otp = st.text_input("Enter OTP", key=f"otp{rid}")

                if st.button(f"📦 Deliver Order ({loc1} → {loc2})", key=f"d{rid}"):
                    if entered_otp == otp:
                        c.execute("UPDATE requests SET status='Delivered' WHERE id=?", (rid,))
                        conn.commit()
                        st.success("✅ Delivered Successfully")
                        st.rerun()
                    else:
                        st.error("❌ Incorrect OTP")

            elif status=="Rejected":
                st.error(f"❌ {loc1} → {loc2} Rejected")

    # ---------------- DASHBOARD ----------------
    if page=="Dashboard":

        if role=="Customer":
            st.title("📊 My Orders")

            c.execute("SELECT * FROM requests WHERE username=?", (user,))
            for r in c.fetchall():
                rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp = r

                st.write(f"🆔 {rid} | {status} | {loc1} → {loc2}")

                if status=="Delivered":
                    if st.button(f"Confirm Delivery {rid}"):
                        c.execute("UPDATE requests SET status='Completed', payment_status='Released' WHERE id=?", (rid,))
                        conn.commit()

                        rating = st.slider(f"Rate Host {rid}",1,5,key=f"rate_{rid}")
                        if st.button(f"Submit Rating {rid}"):
                            c.execute("INSERT INTO ratings VALUES(NULL,?,?,?,?)",(rid,user,host,rating))
                            conn.commit()
                            st.success("Rating submitted!")

        if role=="Host":
            st.title("📊 Host Dashboard")

            c.execute("SELECT SUM(price) FROM requests WHERE host=? AND payment_status='Released'", (user,))
            st.metric("💰 Earnings", f"₹{c.fetchone()[0] or 0}")

    # ---------------- HISTORY ----------------
    if page=="History":
        st.title("📜 Order History")

        if role=="Customer":
            c.execute("SELECT * FROM requests WHERE username=?",(user,))
        else:
            c.execute("SELECT * FROM requests WHERE host=?",(user,))

        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp = r

            st.write(f"""
            🆔 {rid}
            📍 {loc1} → {loc2}
            📦 {bags} bags
            📅 {pdate} → {ddate}
            💰 ₹{price}
            🚦 {status}
            """)

    # ---------------- HELP ----------------
    if page=="Help Line":
        st.title("🆘 Help")

        st.write("📞 +91 9876543210")
        st.write("📧 support@luggageai.com")
        st.write("• Confirm to release payment")
        st.write("• Rating builds trust")