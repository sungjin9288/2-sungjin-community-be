from mangum import Mangum

from app.main import app

# AWS Lambda entrypoint for FastAPI container runtime.
handler = Mangum(app)
