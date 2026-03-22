# get_domain_names.py — run once to print all domain names from your DB
# Usage: python get_domain_names.py

from db import get_db
from sqlalchemy import text

db = next(get_db())
rows = db.execute(text("SELECT domain FROM public.domains ORDER BY domain")).fetchall()
for row in rows:
    print(row[0])