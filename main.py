from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import openai
import os
import sqlite3
from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Assuming you have a Base class where your models are defined
from models import Base
Base.metadata.create_all(bind=engine)

# Load environment variables
load_dotenv()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize FastAPI app
app = FastAPI()

# CORS setup to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set specific frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from twilio.rest import Client

def send_sms(to, message):
    try:
        # Your Twilio credentials
        twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

        # Create a Twilio client
        client = Client(twilio_account_sid, twilio_auth_token)

        # Send the SMS
        message = client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=to
        )
        return {"status": "success", "message": message.sid}
    except Exception as e:
        return {"status": "error", "error": str(e)}

import logging

logging.basicConfig(level=logging.DEBUG)

def send_sms(to, message):
    try:
        twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

        client = Client(twilio_account_sid, twilio_auth_token)

        message = client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=to
        )
        logging.info(f"Message sent successfully with SID: {message.sid}")
        return {"status": "success", "message": message.sid}
    except Exception as e:
        logging.error(f"Error sending message: {str(e)}")
        return {"status": "error", "error": str(e)}

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

# Initialize the database
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

# Test endpoint to verify API is live
@app.get("/")
def home():
    return {"message": "Ai Concierge is live!"}

# SMS handling endpoint (Twilio)
@app.post("/sms")
async def sms_reply(request: Request):
    form = await request.form()
    user_message = form.get("Body", "").strip()
    user_phone = form.get("From", "").strip()
    
    response_text = get_response(user_message, user_phone)
    
    resp = MessagingResponse()
    resp.message(response_text)
    return str(resp)

# Secure API endpoint for adding property details
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

# Chatbot endpoint for frontend
@app.get("/chatbot")
def chatbot_response(query: str, phone: str = ""):
    response_text = get_response(query, phone)
    return {"response": response_text}
