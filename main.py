import os
import logging
from bs4 import BeautifulSoup
from pyrogram import Client
from PIL import Image
from config import *  # Sensitive data handled here
from database import *  # Database interaction functions here
import asyncio
import time
import requests
from alive import keep_alive
from datetime import datetime
from urllib.parse import urljoin

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("Jav.log"),
        logging.StreamHandler()
    ]
)

# Silence unnecessary logs
for module in ["pyrogram", "werkzeug", "flask"]:
    logging.getLogger(module).setLevel(logging.WARNING)

keep_alive()

# MongoDB setup
db = connect_to_mongodb(DATABASE, "Spidydb")
collection_name = COLLECTION_NAME

# Pyrogram client setup
app = Client("SpidyJav", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=10)

def safe_requests(url, retries=3, timeout=10):
    """ A generic retry mechanism for making requests. """
    for _ in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logging.error(f"Request failed for {url}: {e}")
            time.sleep(2)
    return None

def download_and_compress_image(img_url, save_path=None):
    """ Download and compress the image from URL. """
    try:
        save_path = save_path or f"compressed_{int(time.time())}.jpg"
        response = safe_requests(img_url)
        if not response:
            return None
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        with Image.open(save_path) as img:
            img = img.convert("RGB") if img.mode == "RGBA" else img
            img.save(save_path, "JPEG")
        return save_path
    except Exception as e:
        logging.error(f"Error compressing image {img_url}: {e}")
        return None

async def handle_image_upload_or_update(app, name, image_url, category, url):
    """ Handle both uploading new images and updating existing ones. """
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        caption = f"Name: {name.upper()}\nCategory: {category}\n[Torrent]({url})\nDate & Time: {now}"
        local_path = download_and_compress_image(image_url)
        
        if not local_path:
            return
        
        data = get_info(db, collection_name, name)
        if data:  # Update existing message
            if data["TORRENT"] != url:
                await edit_message_if_different(app, LOG_ID, data["ID"], caption)
        else:  # Upload new image
            message = await app.send_photo(LOG_ID, photo=local_path, caption=caption)
            insert_document(db, collection_name, {"ID": message.id, "NAME": name, "IMG": image_url, "TORRENT": url})

    except Exception as e:
        logging.error(f"Error handling image upload or update: {e}")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

async def edit_message_if_different(app, chat_id, message_id, new_caption):
    """ Edit message only if the new caption is different from the current one. """
    try:
        message = await app.get_messages(chat_id, message_id)
        if message.caption != new_caption:
            await app.edit_message_caption(chat_id, message_id, new_caption)
            logging.info(f"Message {message_id} updated.")
        else:
            logging.info(f"Message {message_id} not modified (same content).")
    except Exception as e:
        logging.error(f"Error editing message {message_id}: {e}")

async def scrape_torrents_images_from_pages(app, base_url, page_url, category):
    """ Generic function to scrape torrents and images from pages like tags, actress, and others. """
    response = safe_requests(page_url)
    if not response:
        logging.error(f"Failed to fetch URL: {page_url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    logging.info(f"Scraping started for: {page_url}")
    
    routes = [tag.get('href') for tag in soup.find_all('a') if "/torrent/" in tag.get('href', '')]
    
    # Handle subpages for both tags and actress
    for tag in soup.find_all('a', href=True):
        if ("/tag/" in tag['href'] or "/actress/" in tag['href']) and base_url not in tag['href']:
            sub_response = safe_requests(urljoin(base_url, tag['href']))
            if not sub_response:
                continue
            sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
            routes += [sub_tag['href'] for sub_tag in sub_soup.find_all('a', href=True) if "/torrent/" in sub_tag['href']]

    # Process found routes
    for route in routes:
        try:
            torrent_page = safe_requests(urljoin(base_url, route))
            if not torrent_page:
                continue
            page_soup = BeautifulSoup(torrent_page.text, 'html.parser')
            torrent_url = urljoin(base_url, next(tag['href'] for tag in page_soup.find_all('a') if ".torrent" in tag['href']))
            image_url = next((img['src'] for img in page_soup.find_all('img') if img['src'].startswith("http")), None)
            name = route.split("/")[2]
            if image_url:
                await handle_image_upload_or_update(app, name, image_url, category, torrent_url)
        except Exception as e:
            logging.error(f"Error processing {route}: {e}")

async def main():
    async with app:
        # Scrape popular pages
        page = 1
        while True:
            pop_url = f"https://onejav.com/popular/?page={page}"
            logging.info(f"Scraping popular page: {pop_url}")
            await scrape_torrents_images_from_pages(app, 'https://onejav.com', pop_url, "Popular")
            page += 1

        # Scrape homepage, tags, and actress pages
        await scrape_torrents_images_from_pages(app, 'https://onejav.com', 'https://onejav.com', "Home Page")
        await scrape_torrents_images_from_pages(app, 'https://onejav.com', 'https://onejav.com/tag', "Tags")
        await scrape_torrents_images_from_pages(app, 'https://onejav.com', 'https://onejav.com/actress', "Actress")

        # Scrape random videos
        for _ in range(5):
            await scrape_torrents_images_from_pages(app, 'https://onejav.com', "https://onejav.com/random", "Random Videos")
        
        logging.info("Sleeping for 1 hour...")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    logging.info("Bot Started...")
    app.run(main())
