import os

# Bind to the port Render assigns via $PORT, default 8080 for local dev
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = 2
timeout = 120
accesslog = "-"
errorlog = "-"
