from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.services.stripe_service import StripeService
from app.services.user_service import UserService

router = APIRouter(prefix="/stripe", tags=["stripe"])

stripe_service = StripeService()

@router.post("/create-checkout-session")
async def create_checkout_session(
    user_id: str,
    success_url: str = "http://localhost:3000/success",
    cancel_url: str = "http://localhost:3000/cancel",
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for premium upgrade."""
    
    # Get user information
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already premium
    if user.plan_type == "premium":
        raise HTTPException(status_code=400, detail="User already has premium plan")
    
    # Create checkout session
    checkout_url = stripe_service.create_checkout_session(
        user_id=user_id,
        user_email=f"{user.phone_number}@example.com",  # You might want to add email field to User model
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    if not checkout_url:
        raise HTTPException(status_code=500, detail="Error creating checkout session")
    
    return {"checkout_url": checkout_url}

@router.post("/create-portal-session")
async def create_portal_session(
    user_id: str,
    return_url: str = "http://localhost:3000/dashboard",
    db: Session = Depends(get_db)
):
    """Create a customer portal session for subscription management."""
    
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.plan_type != "premium":
        raise HTTPException(status_code=400, detail="User doesn't have premium plan")
    
    # In a real application, you would store the Stripe customer ID
    # For now, we'll assume it's stored in a user field or separate table
    customer_id = "cus_example"  # This should come from your database
    
    portal_url = stripe_service.create_customer_portal_session(
        customer_id=customer_id,
        return_url=return_url
    )
    
    if not portal_url:
        raise HTTPException(status_code=500, detail="Error creating portal session")
    
    return {"portal_url": portal_url}

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    event = stripe_service.construct_webhook_event(payload, sig_header)
    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    
    # Handle different event types
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Get user ID from metadata
        user_id = session.get('client_reference_id')
        if user_id:
            # Update user to premium plan
            from app.core.schemas import UserUpdate
            user_update = UserUpdate(plan_type="premium")
            UserService.update_user(db, user_id, user_update)
            
            print(f"User {user_id} upgraded to premium")
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        
        # You would need to find user by customer ID
        # For now, we'll just log it
        print(f"Subscription {subscription['id']} was cancelled")
        
        # In a real app, you would:
        # 1. Find user by customer_id
        # 2. Update plan_type back to "free"
    
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        
        # Handle successful payment (subscription renewal)
        print(f"Payment succeeded for subscription: {invoice.get('subscription')}")
    
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        
        # Handle failed payment
        print(f"Payment failed for subscription: {invoice.get('subscription')}")
        
        # You might want to:
        # 1. Send notification to user
        # 2. Potentially downgrade plan after grace period
    
    return {"status": "success"}

@router.get("/subscription-status/{user_id}")
async def get_subscription_status(user_id: str, db: Session = Depends(get_db)):
    """Get subscription status for a user."""
    
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.plan_type != "premium":
        return {
            "plan_type": "free",
            "status": "active",
            "transactions_limit": 50,
            "transactions_used": UserService.get_user_transaction_count_this_month(db, user_id)
        }
    
    # For premium users, you would fetch actual Stripe subscription data
    # This is a simplified response
    return {
        "plan_type": "premium", 
        "status": "active",
        "transactions_limit": "unlimited",
        "transactions_used": UserService.get_user_transaction_count_this_month(db, user_id)
    }