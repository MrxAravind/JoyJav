import subprocess
import os
import logging
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from PIL import Image
from config import *  # Ensure sensitive data like API keys are managed securely
from database import *  # Make sure the database functions are correctly implemented
import asyncio
import time
import requests
from alive import keep_alive
from datetime import datetime
from urllib.parse import urljoin

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("Jav.log"),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)

# Suppress Pyrogram logs
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('flask').setLevel(logging.WARNING)

keep_alive()

# MongoDB setup
database_name = "Spidydb"
db = connect_to_mongodb(DATABASE, database_name)
collection_name = COLLECTION_NAME

# Pyrogram client
app = Client("SpidyJav", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=10)

async def safe_requests(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise an error for bad responses
            return response
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == retries - 1:
                return None  # Return None after exhausting retries
            await asyncio.sleep(2)  # Wait before retrying

# Get image URLs and torrent links from a Jav Website
async def scrape_torrents_and_images(app, url):
    links = []
    routes = []
    base_url = 'https://onejav.com'
    try:
        response = await safe_requests(url)
        if response is None:
            logging.error(f"Failed to fetch base URL {base_url}")
            return links

        soup = BeautifulSoup(response.text, 'html.parser')
        a_tags = soup.find_all('a')
        logging.info("Scraper Started...")

        # Find all relevant links
        for tag in a_tags:
            href = tag.get('href')
            if href and "/torrent/" in href:
                routes.append(href)
            elif href and "/actress/" in href and "/actress/" != href:
                try:
                    sub_response = await safe_requests(base_url + href)
                    if sub_response is None:
                        logging.error(f"Failed to fetch actress page {href}")
                        continue

                    sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
                    sub_a_tags = sub_soup.find_all('a')
                    for sub_tag in sub_a_tags:
                        sub_href = sub_tag.get('href')
                        if sub_href and "/torrent/" in sub_href:
                            routes.append(sub_href)
                except Exception as e:
                    logging.error(f"Error fetching actress page {href}: {e}")

        # Process each route to extract torrent links and associated images
        for route in routes:
            try:
                response = await safe_requests(base_url + route)
                if response is None:
                    logging.error(f"Failed to fetch route {route}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                a_tags = soup.find_all('a')
                imgs = [tag.get('src') for tag in soup.find_all('img')]
                for tag in a_tags:
                    href = tag.get('href')
                    if href and ".torrent" in href:
                        full_torrent_url = base_url + href
                        name = href.split("/")[2]
                        image_url = [
                            img for img in imgs if any(ext in img for ext in ['jpg', 'jpeg', 'png'])
                            and img.startswith("http")
                        ]
                        if len(image_url) != 0:
                            image_url = next((img for img in image_url if await safe_requests(img)), None)
                            if image_url and not check_db(db, collection_name, name):
                                links.append([name, image_url, full_torrent_url])
                                await upload_image(app, name, image_url, full_torrent_url)
                            else:
                                data = get_info(db, collection_name, name)
                                query = {"NAME": data["NAME"]}
                                new_values = {"$set": {"TORRENT": full_torrent_url}}
                                update_message = update_document(db, collection_name, query, new_values)
                                if data["TORRENT"] != full_torrent_url:
                                    now = datetime.now()
                                    date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                                    cap = f"Name: {name.upper()}\n[Torrent]({full_torrent_url})\nDate & Time: {date_time_str}"
                                    await app.edit_message_caption(LOG_ID, data["ID"], cap)
                                    await asyncio.sleep(2)
                                logging.info(update_message)
                                logging.info(f"NAME : {name}")
            except Exception as e:
                logging.error(f"Error processing route {route}: {e}")
    except Exception as e:
        logging.error(f"Error fetching base URL {base_url}: {e}")
    return links

async def extract_onejav():
    base_url = "https://onejav.com"
    tag_url = "https://onejav.com/tag"
    torrent_data = []

    # Function to fetch and parse a URL
    async def fetch_page(url):
        response = await safe_requests(url)
        return BeautifulSoup(response.content, 'html.parser') if response else None

    # Process tag pages
    async def process_tags(base_page_url):
        soup = await fetch_page(base_page_url)
        if not soup:
            return
        
        a_tags = soup.find_all('a')
        for tag in a_tags:
            href = tag.get('href')
            if href and "/tag/" in href and base_page_url not in href:
                full_url = urljoin(base_page_url, href)
                logging.info(f"Processing tag page: {full_url}")
                
                try:
                    tag_soup = await fetch_page(full_url)
                    if tag_soup:
                        await extract_torrent_links_images_and_names(tag_soup)
                except Exception as e:
                    logging.error(f"Error processing tag page {full_url}: {e}")

    # Process actress pages
    async def process_actress(base_page_url):
        soup = await fetch_page(base_page_url)
        if not soup:
            return
        
        a_tags = soup.find_all('a')
        for tag in a_tags:
            href = tag.get('href')
            if href and "/actress/" in href and base_page_url not in href:
                full_url = urljoin(base_page_url, href)
                logging.info(f"Processing actress page: {full_url}")
                
                try:
                    actress_soup = await fetch_page(full_url)
                    if actress_soup:
                        await extract_torrent_links_images_and_names(actress_soup)
                except Exception as e:
                    logging.error(f"Error processing actress page {full_url}: {e}")

    # Extract torrent links, associated images, and names from a soup object
    async def extract_torrent_links_images_and_names(soup):
        a_tags = soup.find_all('a')
        imgs = soup.find_all('img')

        for tag in a_tags:
            href = tag.get('href')
            # Extracting torrent links
            if href and ".torrent" in href:
                try:
                    full_torrent_url = urljoin(base_url, href)
                    name = href.split("/")[2]  # Assuming the name is the 3rd part of the URL structure
                    image_url = [
                        img.get('src') for img in imgs if any(ext in img.get('src') for ext in ['jpg', 'jpeg', 'png'])
                        and img.get('src').startswith("http") and name.lower() in img.get('src')
                    ]
                    image_url = image_url[0] if image_url else None  # Use the first valid image

                    if full_torrent_url not in [data['torrent'] for data in torrent_data]:
                        if image_url and not check_db(db, collection_name, name):
                            torrent_data.append({
                                "name": name,
                                "torrent": full_torrent_url,
                                "image": image_url
                            })
                            await upload_image(app, name, image_url, full_torrent_url)
                        else:
                            data = get_info(db, collection_name, name)
                            query = {"NAME": data["NAME"]}
                            new_values = {"$set": {"TORRENT": full_torrent_url}}
                            update_message = update_document(db, collection_name, query, new_values)
                            if data["TORRENT"] != full_torrent_url:
                                now = datetime.now()
                                date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                                cap = f"Name: {name.upper()}\n[Torrent]({full_torrent_url})\nDate & Time: {date_time_str}"
                                await app.edit_message_caption(LOG_ID, data["ID"], cap)
                                await asyncio.sleep(2)
                            logging.info(update_message)
                            logging.info(f"NAME : {name}")
                    #logging.info(f"Found torrent: {full_torrent_url}, name: {name}, image: {image_url}")
                except Exception as e:
                    logging.error(f"Error processing torrent link {href} | {name}-{full_torrent_url} - {image_url}: {e}")
                

    # Start scraping both tag and actress pages
    logging.info("Processing Tag Pages...")
    try:
        await process_tags(tag_url)
    except Exception as e:
        logging.error(f"Error processing tag pages: {e}")

    logging.info("Processing Actress Pages...")
    actress_url = "https://onejav.com/actress"
    try:
        await process_actress(actress_url)
    except Exception as e:
        logging.error(f"Error processing actress pages: {e}")

    return torrent_data

# Download and compress image
def download_and_compress_image(img_url, save_path=None):
    if save_path is None:
        save_path = f"compressed_{int(time.time())}.jpg"
    try:
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            with Image.open(save_path) as img:
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(save_path, "JPEG")
            return save_path
        else:
            logging.error(f"Failed to download image {img_url}, status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Failed to download or compress image {img_url}: {e}")
        return None

async def upload_image(app, name, image_url, url):
    local_path = None
    try:
        local_path = download_and_compress_image(image_url)
        if local_path:
            now = datetime.now()
            date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            cap = f"Name: {name.upper()}\n[Torrent]({url})\nDate & Time: {date_time_str}"
            message = await app.send_photo(
                LOG_ID, photo=local_path,
                caption=cap
            )
            result = {"ID": message.id, "NAME": name, "IMG": image_url, "TORRENT": url}
            insert_document(db, collection_name, result)
            logging.info(f"Posted Jav : {name}")
    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

# Async main function to process torrent links and images
async def main():
    async with app:
        if True:
            page = 1
            logging.info(f"Scraping Page: New Method")
            torrent_data = await extract_onejav()
            while True:
                pop_url = f"https://onejav.com/popular/?page={page}"
                logging.info(f"Scraping Page : {pop_url}")
                links = await scrape_torrents_and_images(app, pop_url)
                if len(links) == 0:
                    break
                page += 1
            logging.info(f"Scraping Page : Home")
            base_url = 'https://onejav.com'
            links = await scrape_torrents_and_images(app, base_url)
            random_url = "https://onejav.com/random"
            for i in range(5):
                links = await scrape_torrents_and_images(app, random_url)
            logging.info("Sleeping for 1 Hour....")
            await asyncio.sleep(3600)  # Sleep for 1 hour

# Running the Pyrogram app
if __name__ == "__main__":
    logging.info("Bot Started...")
    app.run(main())
