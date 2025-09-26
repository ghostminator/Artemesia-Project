import hmac, hashlib
SECRET = b"your-very-secret-key"
print(hmac.new(SECRET, b"licensed-user", hashlib.sha256).hexdigest().upper())
