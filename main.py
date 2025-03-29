from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import sqlite3
from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set
    uvicorn.run(app, host="0.0.0.0", port=port)

# Load environment variables
load_dotenv()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")  # Secure API key for adding properties

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
    return {"message": "FastAPI is live!"}

# SMS handling endpoint (Twilio)
@app.post("/sms")
async def sms_reply(request: Request):
    form = await request.form()
    user_message = form.get("Body", "").strip()
    user_phone = form.get("From", "").strip()

    print(f"User Message: {user_message}")
    print(f"User Phone: {user_phone}")
    
    response_text = get_response(user_message, user_phone)

    print(f"Response Text: {response_text}")
    
    resp = MessagingResponse()
    resp.message(response_text)
    return str(resp)

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

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
