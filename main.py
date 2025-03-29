from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from twilio.rest import Client
import openai
import os
import logging

# Set up logging for better error tracking
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app
app = FastAPI()

# Models for Property and SMS requests
class Property(BaseModel):
    name: str
    location: str
    description: str
    price_per_night: float
    available: bool

class SMSRequest(BaseModel):
    to: str
    message: str

# In-memory storage for properties (you could replace this with a database like SQLite or MongoDB later)
properties_db = []

# Root endpoint for health check or general information
@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Concierge API!"}

# POST endpoint to create a property
@app.post("/property")
async def create_property(property: Property):
    properties_db.append(property)
    logging.info(f"Created new property: {property.name}")
    return {"status": "success", "property": property}

# GET endpoint to list all properties
@app.get("/properties")
async def list_properties():
    if not properties_db:
        raise HTTPException(status_code=404, detail="No properties found.")
    return properties_db

# POST endpoint to send SMS via Twilio
@app.post("/sms")
async def send_sms(request: SMSRequest):
    # Fetch Twilio credentials from environment variables
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    # Check if Twilio credentials are missing
    if not account_sid or not auth_token or not from_number:
        raise HTTPException(status_code=400, detail="Twilio credentials are not set properly.")
    
    # Initialize Twilio client
    client = Client(account_sid, auth_token)

    try:
        # Send the SMS
        message = client.messages.create(
            body=request.message,
            from_=from_number,
            to=request.to
        )
        # Return response with the SID of the sent message
        return {"status": "Message sent", "message_sid": message.sid}
    except Exception as e:
        # Catch and return any exceptions that occur during the SMS send process
        logging.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# POST endpoint to integrate OpenAI for AI-generated responses (for instance, assistant)
@app.post("/ask_ai")
async def ask_ai(question: str):
    # Fetch OpenAI API key from environment variable
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Check if OpenAI API key is missing
    if not openai.api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is not set properly.")
    
    try:
        # Request OpenAI for completion (you can customize the model as needed)
        response = openai.Completion.create(
            model="text-davinci-003",  # You can use other models such as GPT-4
            prompt=question,
            max_tokens=150
        )
        return {"response": response.choices[0].text.strip()}
    except Exception as e:
        logging.error(f"Error with OpenAI: {str(e)}")
        raise HTTPException(status_code=500, detail="Error while interacting with OpenAI.")

# Optional additional endpoint for testing Twilio setup (you could add more routes here as needed)
@app.get("/test")
def test():
    return {"status": "Test endpoint working"}
