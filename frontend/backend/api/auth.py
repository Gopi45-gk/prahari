import random
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

RESEND_API_KEY = "re_aqhX7n29_Fng5FuVdW1TmecgF6okusdaA"
otp_store = {}

auth_router = APIRouter()

class OTPRequest(BaseModel):
    email: str

class OTPVerify(BaseModel):
    email: str
    otp: str

@auth_router.post("/auth/request-otp")
async def request_otp(req: OTPRequest):
    otp = str(random.randint(100000, 999999))
    otp_store[req.email] = otp
    print(f"\n[PRAHARI AUTH] OTP for {req.email} is: {otp}\n")

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": "PRAHARI Security <onboarding@resend.dev>",
                    "to": req.email,
                    "subject": "PRAHARI Authority Login OTP",
                    "html": f"<p>Your secure OTP is: <strong>{otp}</strong></p><p>This OTP is valid for 5 minutes.</p>"
                }
            )
            print("[PRAHARI AUTH] Resend API Response:", res.status_code, res.text)
        except Exception as e:
            print("[PRAHARI AUTH] Failed to send email:", e)

    return {"message": "OTP sent"}

@auth_router.post("/auth/verify-otp")
def verify_otp(req: OTPVerify):
    expected_otp = otp_store.get(req.email)
    if not expected_otp or expected_otp != req.otp:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

    del otp_store[req.email]
    return {"message": "OTP verified successfully"}
