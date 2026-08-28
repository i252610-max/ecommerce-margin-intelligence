from dotenv import load_dotenv
import os
load_dotenv()
print(os.getenv("ALERT_WEBHOOK_URL"))  # Should print None or empty