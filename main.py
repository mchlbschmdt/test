from fastapi import FastAPI, Request, Depends, HTTPException
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")  # New security key

# Initialize FastAPI app
app = FastAPI()

# OpenAI API Setup
openai.api_key = OPENAI_API_KEY

# Database setup
DB_PATH = "properties.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS property_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            wifi TEXT,
            check_in TEXT,
            checkout TEXT,
            recommendations TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_property_info(phone):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT wifi, check_in, checkout, recommendations FROM property_info WHERE phone = ?", (phone,))
    result = cursor.fetchone()
    conn.close()
    return result

# Initialize DB
init_db()

# Function to process guest queries
def get_response(user_input, phone):
    property_data = get_property_info(phone)
    if property_data:
        wifi, check_in, checkout, recommendations = property_data
        PROPERTY_INFO = {
            "wifi": wifi,
            "check-in": check_in,
            "checkout": checkout,
            "recommendations": recommendations
        }
        for key in PROPERTY_INFO:
            if key in user_input.lower():
                return PROPERTY_INFO[key]
    
    # If no predefined answer, use AI
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are a helpful concierge for an Airbnb rental."},
                  {"role": "user", "content": user_input}]
    )
    return response["choices"][0]["message"]["content"]

@app.post("/sms")
async def sms_reply(request: Request):
    form = await request.form()
    user_message = form.get("Body", "").strip()
    user_phone = form.get("From", "").strip()
    
    response_text = get_response(user_message, user_phone)
    
    resp = MessagingResponse()
    resp.message(response_text)
    return str(resp)

# Secure API endpoint for adding properties
@app.post("/add_property")
async def add_property(
    phone: str, wifi: str, check_in: str, checkout: str, recommendations: str, 
    request: Request
):
    api_key = request.headers.get("X-API-KEY")
    if api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO property_info (phone, wifi, check_in, checkout, recommendations) 
            VALUES (?, ?, ?, ?, ?)
        """, (phone, wifi, check_in, checkout, recommendations))
        conn.commit()
        conn.close()
        return {"message": "Property added successfully!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Property with this phone number already exists.")
