# gunicorn.conf.py

bind = "0.0.0.0:10000"   # Render listens on port 10000
workers = 3              # Ideal for ~20 users on 1 CPU
threads = 2              # Handle concurrent requests
timeout = 120            # Prevent premature worker kill
accesslog = "-"          # Show logs in Render dashboard
errorlog = "-"
loglevel = "info"
