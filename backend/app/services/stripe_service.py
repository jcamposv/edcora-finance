import stripe
import os
from typing import Optional, Dict, Any

class StripeService:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        # Premium plan price ID (create this in Stripe Dashboard)
        self.premium_price_id = os.getenv("STRIPE_PREMIUM_PRICE_ID", "price_premium_monthly")
    
    def create_checkout_session(self, user_id: str, user_email: str, success_url: str, cancel_url: str) -> Optional[str]:
        """Create a Stripe checkout session for premium subscription."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.premium_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=user_id,
                customer_email=user_email,
                metadata={
                    'user_id': user_id
                }
            )
            
            return session.url
            
        except Exception as e:
            print(f"Error creating checkout session: {e}")
            return None
    
    def create_customer_portal_session(self, customer_id: str, return_url: str) -> Optional[str]:
        """Create a customer portal session for subscription management."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            
            return session.url
            
        except Exception as e:
            print(f"Error creating portal session: {e}")
            return None
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> Optional[Dict[Any, Any]]:
        """Construct and verify webhook event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
            
        except ValueError as e:
            print(f"Invalid payload: {e}")
            return None
        except stripe.error.SignatureVerificationError as e:
            print(f"Invalid signature: {e}")
            return None
    
    def get_subscription_status(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription details from Stripe."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            return {
                'id': subscription.id,
                'status': subscription.status,
                'customer': subscription.customer,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end,
            }
            
        except Exception as e:
            print(f"Error retrieving subscription: {e}")
            return None
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription at the end of the current period."""
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return True
            
        except Exception as e:
            print(f"Error canceling subscription: {e}")
            return False