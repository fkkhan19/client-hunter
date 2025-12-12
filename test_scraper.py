from app import create_app
from app.scraper.google_maps_new import get_map_results

app = create_app()

with app.app_context():
    get_map_results("mobile repair", "Pune", max_results=5)
