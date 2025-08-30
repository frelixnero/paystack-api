# Paystack Payment Integration with FastAPI and Flutter

This guide explains how to integrate Paystack into a Flutter app using a FastAPI backend. It covers initiating a payment, verifying the transaction, and handling deep links to notify the app of a successful payment.

## Prerequisites

- A Paystack account
- FastAPI backend set up
- Flutter app with `app_links` and `url_launcher` packages
- Firebase Dynamic Links (optional for deep linking)

---

## 1. Setting Up Paystack

1. Sign up at [Paystack](https://paystack.com/).
2. Obtain your **Public Key** and **Secret Key** from the Paystack dashboard.
3. Ensure your webhook is set up (if required) in Paystack settings.

---

## 2. FAST API BACKEND SETUP

### Install Dependencies

```bash
pip install fastapi uvicorn requests
```

### Create the Backend Server

```python
import json
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAYSTACK_SECRET_KEY = "sk_test_b7cd2c954773710b5192710f443dce91446cb0c0"
APP_URL_SCHEME = "myapp"  # Your app's URL scheme

class PaymentRequest(BaseModel):
    email: str
    amount: float

@app.post("/paystack/initialize/")
async def initialize_payment(payment: PaymentRequest):
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": payment.email,
        "amount": int(payment.amount * 100),  # Convert amount to kobo
        "callback_url": "http://192.168.48.153:8000/paystack/callback", # change to your backend call back url
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        response_json = response.json()
        raise HTTPException(status_code=response.status_code, detail=response_json.get("message", "Payment initialization failed"))


### VERIFY PAYMENTS
@app.get("/paystack/verify/{reference}")
async def verify_payment(reference: str):
    print(f"Verifying payment with reference: {reference}")
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    print(f"Paystack API response status code: {response.status_code}")
    print(f"Paystack API response content: {response.json()}")  # Add this line
    if response.status_code == 200:
        data = response.json()
        if data["data"]["status"] == "success":
            return {"status": "success", "message": "Payment successful", "data": data}
        else:
            return {"status": "failed", "message": "Payment not successful", "data": data}
    raise HTTPException(status_code=400, detail="Failed to verify payment")


#$# WE USE THIS IF RESPONSSE FROM PAYSTACK OR FINANCE PROVIDER IS POST NOT GET
@app.post("/paystack/callback")
async def paystack_callback_post(request: Request):
    return await process_callback(request)


### FOR GET RESPONSE FROM PAYSTACK
@app.get("/paystack/callback")
async def paystack_callback_get(trxref: str = Query(None), reference: str = Query(None)):
    if reference:
        verification_result = await verify_payment(reference)
        if verification_result.get("status") == "success":
            APP_URL_SCHEME = "myapp"

            return RedirectResponse(url=f"{APP_URL_SCHEME}://payment-success?reference={reference}", status_code=302)
        else:
            return RedirectResponse(url="https://yourfrontend.com/payment-failed")

    return Response(status_code=400, content="Invalid callback")
    

# use if response is post not get
async def process_callback(request: Request):
    try:
        payload = await request.json() if request.method == "POST" else {}
        print(f"Received payload: {payload}")
        reference = payload.get("data", {}).get("reference")
        if reference:
            verification_result = await verify_payment(reference)
            if verification_result.get("status") == "success":
                deep_link_url = f"{APP_URL_SCHEME}://payment?reference={reference}"
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Redirecting...</title>
                    <script>
                        window.location.replace('{deep_link_url}');
                    </script>
                </head>
                <body>
                    <p>Redirecting to app...</p>
                </body>
                </html>
                """
                return HTMLResponse(content=html_content)
            else:
                return Response(status_code=400, content="Payment verification failed")
        else:
            return Response(status_code=400, content="Invalid callback payload")
    except Exception as e:
        print(f"Error processing callback: {e}")
        return Response(status_code=400, content="Invalid callback payload")

```----



**Endpoints:**

- `POST /paystack/initiate` → Initializes a payment and returns a checkout URL.
- `GET /paystack/verify/{reference}` → Verifies a transaction using the reference.

---




## 3. FLUTTER APP INTEGRATION

### Add Dependencies

```yaml
dependencies:
  url_launcher: ^6.0.20
  app_links: ^3.4.3
```

### Open Payment Page in BROWSER

```dart
THIS FUNCTION HANDLES PAYMENT TO PYSTSCK. CALL IT IN YOUR "PAY BUTTON"
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';

void userTapped() async {
    print("this is the price$_formatPrice()");
    if (formKey.currentState!.validate()) {
      final url = Uri.parse('http://192.168.48.153:8000/paystack/initialize/');

      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"email": useremail!, "amount": "put price here"}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final Uri checkoutUri = Uri.parse(data["data"]["authorization_url"]);

        try {
          if (await canLaunchUrl(checkoutUri)) {
            await launchUrl(checkoutUri, mode: LaunchMode.externalApplication);
          } else {
            throw 'Could not launch $checkoutUri';
          }
        } catch (e) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text("Error launching URL: $e")));
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Payment initialization failed")),
        );
      }
    }
  }

#### INITIALIZE the paymennt verification wwith an init state : It automatically run when app link redirects ou back to your app.
#### It should be placed where your in the same page as your VERIFY PAYMENT method for 
// initialize
  @override
  void initState() {
    super.initState();
    if (widget.reference != null) {
      //Verify payment if reference is passed.
      verifyPayment(context, widget.reference);
    }
  }


@#### CREATE THE PAYMENT VERIFYING MEHTOD TO INTERACT WITH YOUR FASTAPI BACKEND
//VERIFY PAYMENT
Future<void> verifyPayment(BuildContext context, String reference) async {
    print(
      "Starting payment verification for reference: $reference",
    ); // Log the start

    final url = Uri.parse(
      'http://192.168.48.153:8000/paystack/verify/$reference',
    );

    print("Verification URL: $url"); // Log the URL

    try {
      final response = await http.get(url);

      print(
        "Verification response status code: ${response.statusCode}",
      ); // Log status code

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        if (data["status"] == "success") {
          // Change this line
          // Payment was successful
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text("Payment successful!")));

          // Navigate to a success page or update UI
          Navigator.push(
            context,
            MaterialPageRoute(builder: (context) => DeliveryProgressPage()),
          );
        } else {
          // Payment failed
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("Payment failed! Please try again.")),
          );
          print("Payment verification failed: ${data["message"]}");
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              "Payment verification failed! Status code: ${response.statusCode}",
            ),
          ),
        );
        print(
          "Payment verification API call failed with status code: ${response.statusCode}",
        );
      }
    } catch (e) {
      print("Error during payment verification: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Payment verification failed! An error occurred."),
        ),
      );
    }
  }

```



---

## 4. HANDLING DEEP LINKS WITH FLUTTER

### Set Up `app_links` in your main.dart
this is snippet of own code base

```dart
import 'package:delivery_app/services/auth/auth_gate.dart';
import 'package:delivery_app/firebase_options.dart';
import 'package:delivery_app/models/resturant.dart';
import 'package:delivery_app/themes/theme_provider.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:provider/provider.dart';
import 'navigator_key/navigator.dart';
import 'package:app_links/app_links.dart'; // Import app_links
import 'pages/payment_page.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  await dotenv.load(fileName: ".env");
  initAppLinks(); // Initialize app_links

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (context) => ThemeProvider()),
        ChangeNotifierProvider(create: (context) => Resturant()),
      ],
      child: MyApp(),
    ),
  );
}

### Initialize applink
Future<void> initAppLinks() async {
  final _appLinks = AppLinks();

  // Check initial link
  final appLink = await _appLinks.getInitialLink();
  if (appLink != null) {
    handleAppLink(appLink);
  }

  // Handle link changes
  _appLinks.uriLinkStream.listen((uri) {
    handleAppLink(uri);
  });
}

#### handle and app link.Here after applink opens the app it goes back to my payment page with the reference . This triggers the verify method there whci confirms payment
##and then goes to my receipt page
void handleAppLink(Uri uri) {
  String? reference = uri.queryParameters['reference'];
  if (reference != null) {
    print("Deep link received! Reference: $reference");

    NavigationService.navigatorKey.currentState?.push(
      MaterialPageRoute(
        builder: (context) => PaymentPage(reference: reference),
      ),
    );
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: NavigationService.navigatorKey,
      debugShowCheckedModeBanner: false,
      home: AuthGate(),
      theme: Provider.of<ThemeProvider>(context).themeData,
    );
  }
}

```


### Register Deep Link in Android and iOS

**Android (AndroidManifest.xml)**
This block goes into the activity part of your androidmanifest file

```xml
<intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="myapp" android:host="payment-success" />
</intent-filter>
```

**iOS (info.plist)**

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>myapp</string>
        </array>
    </dict>
</array>
```

---

## 5. Testing the Integration

1. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```
	uvicorn main:app --reload --host 0.0.0.0 --port 8080
	
-----uvicorn trial:app --reload --host 0.0.0.0 --port 8080
@@	
####### ----  uvicorn main:app --reload --host 0.0.0.0 --port 8080

2. Run the Flutter app and initiate a payment.
3. Paystack should redirect to `myapp://payment-success?reference=xyz123` after payment.
4. Flutter should capture this deep link and verify the payment with the backend.

---

## Conclusion

This guide provides a complete workflow for integrating Paystack into a Flutter app using FastAPI. By implementing these steps, you can seamlessly handle payments and deep link callbacks efficiently.

