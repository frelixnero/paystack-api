import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import requests
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables from .env file
load_dotenv()

# PAYSTACK_SECRET_KEY = "sk_test_b7cd2c954773710b5192710f443dce91446cb0c0"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
if PAYSTACK_SECRET_KEY is None:
    raise ValueError("PAYSTACK_SECRET_KEY is not set in the .env file")

# APP_URL_SCHEME = "myapp"  # Your app's URL scheme
APP_URL_SCHEME = os.getenv("APP_URL_SCHEME")
if APP_URL_SCHEME is None:
    raise ValueError("APP_URL_SCHEME is not set in the .env file")

class PaymentRequest(BaseModel):
    email: str
    amount: float
    
PROCESSED_PAYMENTS = set() 
# Root route
@app.get("/")
async def root():
    return {"message": "Hello World"}

# @app.post("/paystack/initialize/")
# async def initialize_payment(payment: PaymentRequest):
#     print("Payment Initialization Endpoint hit")
#     headers = {
#         "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
#         "Content-Type": "application/json",
#     }
#     data = {
#         "email": payment.email,
#         "amount": int(payment.amount * 100),  # Convert amount to kob
#         "callback_url": "http://10.154.42.153:8080/paystack/callback", # change to your backend call back url
#     }
#     print("D A T A S E N T to PayS T A C K:", data)
#     response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
#     print("Paystack API response:", response.json())

#     if response.status_code == 200:
#         return response.json()
#     else:
#         response_json = response.json()
#         raise HTTPException(status_code=response.status_code, detail=response_json.get("message", "Payment initialization failed"))
@app.post("/paystack/initialize/")
async def initialize_payment(payment: PaymentRequest):
    print("Payment Initialization Endpoint hit")

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": payment.email,
        "amount": int(payment.amount * 100),  # Convert to kobo
        "callback_url": "https://paystack-api-vblu.onrender.com/paystack/callback",
    }
    print("D A T A S E N T to PayS T A C K:", data)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers,
        )

    print("Paystack API response:", response.json())

    if response.status_code == 200:
        return response.json()
    else:
        response_json = response.json()
        raise HTTPException(
            status_code=response.status_code,
            detail=response_json.get("message", "Payment initialization failed")
        )

@app.get("/paystack/verify/{reference}")
async def verify_payment(reference: str):
    print(f"Verifying payment with reference: {reference}")

    if reference in PROCESSED_PAYMENTS:
        return {"status": "success", "message": "Payment already verified"}

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data["data"]["status"] == "success":
            PROCESSED_PAYMENTS.add(reference)  # Mark as processed
            return {"status": "success", "message": "Payment successful", "data": data}
        else:
            return {"status": "failed", "message": "Payment not successful", "data": data}

    raise HTTPException(status_code=400, detail="Failed to verify payment")



@app.get("/paystack/callback")
async def paystack_callback_get(trxref: str = Query(None), reference: str = Query(None)):
    print(f"Received callback for trxref: {trxref}, reference: {reference}")
    actual_ref = trxref if trxref else reference  # Use trxref if available
    if actual_ref:
        
        verification_result = await verify_payment(actual_ref)
        # print(f"Verification result for {reference}: {verification_result}")
        if verification_result.get("status") == "success":
            APP_URL_SCHEME = "myapp"

            return RedirectResponse(url=f"{APP_URL_SCHEME}://payment-success?reference={reference}", status_code=302)
        else:
            return RedirectResponse(url="https://yourfrontend.com/payment-failed")

    return Response(status_code=400, content="Invalid callback")
    

@app.post("/paystack/webhook")
async def paystack_webhook(request: Request):
    payload = await request.json()
    event = payload.get("event")

    if event == "charge.success":
        reference = payload["data"]["reference"]
        print(f"Received webhook for successful payment: {reference}")

        if reference not in PROCESSED_PAYMENTS:
            PROCESSED_PAYMENTS.add(reference)  # Mark as processed
            return {"status": "success", "message": "Payment recorded"}
    
    return {"status": "ignored", "message": "Unhandled webhook event"}
