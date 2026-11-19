from dotenv import load_dotenv
load_dotenv()
from app import create_app
from app.extensions import db
import app.models  # noqa

with create_app().app_context():
    db.create_all()
    print("Database tables created.")
