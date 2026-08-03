# Subscription Integration Guide

This guide walks through the complete end-to-end flow for integrating
with the weekly digest subscription API.

---

## End-to-End Flow

### Step 1: Subscribe

Send a POST request to subscribe an email address:

    POST /subscribe/
    Content-Type: application/json

    {
        "email": "user@example.com"
    }

Response (200 OK):

    {
        "message": "You're subscribed! You'll receive your first digest next Sunday.",
        "email": "user@example.com"
    }

Response (409 Conflict - already subscribed):

    {
        "detail": "This email is already subscribed to the weekly digest."
    }

---

### Step 2: Email/Webhook Delivery

Once subscribed, the system sends a weekly digest email every Sunday.
The email contains an unsubscribe link:

    https://yourapp.com/subscribe/unsubscribe?email=user@example.com&token=abc123

The token is a unique unsubscribe_token generated at subscription time.

Webhook Callback Testing (Local Development):

    pip install ngrok
    ngrok http 8000

Use the generated URL for webhook testing:

    https://abc123.ngrok.io/subscribe/unsubscribe?email=user@example.com&token=abc123

---

### Step 3: Unsubscribe

Option A - One-Click Link (GET):
User clicks the unsubscribe link in the email:

    GET /subscribe/unsubscribe?email=user@example.com&token=abc123

Response (200 OK):

    {
        "message": "You've been unsubscribed from the weekly digest."
    }

Option B - API Call (POST):

    POST /subscribe/unsubscribe
    Content-Type: application/json

    {
        "email": "user@example.com",
        "token": "abc123"
    }

Response (200 OK):

    {
        "message": "You've been unsubscribed from the weekly digest.",
        "email": "user@example.com"
    }

---

## Subscription Lifecycle Summary

    New Email
        |
        v
    POST /subscribe/  ->  Active Subscription Created
        |
        v
    Weekly Digest Email Sent (every Sunday)
        |
        v
    User Clicks Unsubscribe Link
        |
        v
    GET /subscribe/unsubscribe  ->  Subscription Deactivated
        |
        v
    Re-subscribe Anytime
        |
        v
    POST /subscribe/  ->  Subscription Re-activated (new token issued)

---

## Error Reference

| Status Code | Meaning                      |
|-------------|------------------------------|
| 200         | Success                      |
| 409         | Email already subscribed     |
| 404         | Subscription not found       |
| 403         | Invalid unsubscribe token    |