import os

print("API KEY FOUND:", bool(os.getenv("ALPACA_API_KEY")))
print("SECRET KEY FOUND:", bool(os.getenv("ALPACA_SECRET_KEY")))