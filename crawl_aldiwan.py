import os
import json
import time
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import arabic_reshaper
from bidi.algorithm import get_display

BASE_URL = "https://www.aldiwan.net/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def fix_ar(text):
    """
    Fixes Arabic text rendering for proper display in terminals that don't 
    support right-to-left text.
    """
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def sanitize_filename(name):
    """
    Removes illegal characters (like \ / : * ? " < > |) from strings so they 
    can be safely used as folder or file names.
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    return sanitized.strip()

def get_soup(url):
    """
    Helper function to fetch a URL and return a parsed BeautifulSoup object.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status() # Raises an error for bad HTTP codes (like 404 or 500)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"[-] Error fetching {url}: {e}")
        return None

def get_eras():
    """
    Scrapes the homepage to find the "Eras" (العصور) menu and extracts 
    all Era names and their respective URLs.
    """
    print("[*] Scanning homepage for Eras...")
    soup = get_soup(BASE_URL)
    eras = []
    
    if not soup: 
        return eras

    # Find all h2 tags, looking specifically for the one titled 'تصنيفات العصور'
    headers = soup.find_all('h2')
    for h2 in headers:
        if 'تصنيفات العصور' in h2.text:
            # Move up the HTML tree to the parent container, then find the content box
            era_container = h2.find_parent('div', class_='s-menu').find('div', class_='content')

            # Extract all anchor <a> tags (links) within this specific container
            links = era_container.find_all('a')

            # Build our list of dictionaries containing the Era's name and absolute URL
            for link in links:
                era_name = link.text.strip()
                # urljoin is used to convert relative URLs (like "/era/1") 
                # into absolute URLs ("https://www.aldiwan.net/era/1")
                era_url = urljoin(BASE_URL, link.get('href'))
                eras.append({"name": era_name, "url": era_url})
            
            # Stop searching the page once we've found the target section
            break 
    
    print(f"[+] SUCCESS: Found {len(eras)} Eras in total.\n")
    return eras

def get_poets_in_era(era_url):
    """
    Visits an Era's page and extracts the names and profile URLs of every poet listed
    """
    soup = get_soup(era_url)
    poets = []
    
    # If the page failed to load, we return an empty list. 
    if not soup: 
        return poets
    
    # Find all links on the era page
    links = soup.find_all('a', href=True)
    for link in links:
        href = link['href']
        
        # Al Diwan poet URLs uniquely start with 'cat-poet-'
        if href.startswith('cat-poet-'):
            # The actual readable name is stored inside a <span> with class 'h3'
            name_span = link.find('span', class_='h3')
            if name_span:
                poet_name = name_span.text.strip()
                poet_url = urljoin(BASE_URL, href)
                
                # Prevent adding duplicate poets
                if not any(p['url'] == poet_url for p in poets):
                    poets.append({"name": poet_name, "url": poet_url})
                    
    return poets

def scrape_poem(poem_url):
    """
    Visits a specific poem's page. Extracts the metadata (Rhyme, Meter) 
    and perfectly pairs the left and right hemistiches (halves) of each verse.
    """
    soup = get_soup(poem_url)

    if not soup: 
        return None

    # Set default fallback values in case the website is missing this metadata
    bahr = "غير محدد"
    qafiyah = "غير محدد"
    diwan = "الديوان الرئيسي" 
    
    # Extract Metadata
    # The metadata tags are located at the bottom of the poem inside a '.tips' div
    meta_tags = soup.select('.tips a') 
    for tag in meta_tags:
        text = tag.text.strip()
        if "بحر" in text:
            bahr = text.replace("بحر", "").strip()
        elif "قافية" in text:
            qafiyah = text.replace("قافية", "").strip() 

    verses = []
    
    # Extract Verses
    poem_container = soup.find('div', id='poem_content')
    if poem_container:
        # Al Diwan structures every single half-verse as an <h3> tag in a flat list
        lines = poem_container.find_all('h3')
        
        # Loop through the list of <h3> tags in steps of 2
        # This allows us to pair index [i] (Right side) with index [i+1] (Left side)
        for i in range(0, len(lines), 2):
            h1 = lines[i].text.strip() # Right Hemistich
            
            # Use a safe check (i+1 < len) just in case a poem ends on a single half-verse
            h2 = lines[i+1].text.strip() if i + 1 < len(lines) else "" # Left Hemistich
            
            verses.append({
                "left_hemistich": h2,
                "right_hemistich": h1,
                "full_verse": f"{h1} ... {h2}" if h2 else h1 # If there's no left hemistich, we just use the right one as the full verse
            })
            
    return {
        "bahr": bahr,
        "qafiyah": qafiyah,
        "diwan": diwan,
        "verses": verses
    }

def scrape_poet(poet_url, era_name, poet_name):
    """
    Visits a poet's profile, finds all their poems, creates the necessary directories, 
    and delegates the poem scraping to scrape_poem(), saving the results individually.
    """
    # Create the granular directory structure (raw_data/al_diwan/era_Name/poet_Name/)
    safe_era = sanitize_filename(era_name)
    safe_poet = sanitize_filename(poet_name)
    poet_dir = os.path.join("raw_data", "al_diwan", safe_era, safe_poet)
    
    # exist_ok=True prevents crashes if the folder already exists from a previous run
    os.makedirs(poet_dir, exist_ok=True)
    
    soup = get_soup(poet_url)
    if not soup: 
        return

    # Locate all links pointing to individual poems
    poem_links = soup.select('.record a.float-right')
    if not poem_links:
        print(f"  [!] No poems found for {fix_ar(poet_name)}.")
        return

    print(f"  [>] Scraping {fix_ar(poet_name)}: Found {len(poem_links)} poems.")

    # Loop through all found poems.
    for index, link in enumerate(poem_links, 1):
        href = link.get('href')
        if not href: 
            continue
        
        poem_title = link.text.strip()
        safe_title = sanitize_filename(poem_title)
        
        # Fallback just in case the title was made entirely of illegal characters (e.g. ????)
        if not safe_title: 
            safe_title = f"poem_unnamed_{index}"

        # Define the exact path where this specific poem's JSON will be saved
        file_path = os.path.join(poet_dir, f"{safe_title}.json")

        # If the script crashed previously, this checks if the specific poem file 
        # is already safely on the hard drive. If yes, skip downloading it again!
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"      -> Skipping {index}/{len(poem_links)}: {fix_ar(poem_title)} (Already saved)")
            continue

        full_poem_url = urljoin(BASE_URL, href)
        print(f"      -> Downloading {index}/{len(poem_links)}: {fix_ar(poem_title)}")
        
        # Go get the verses and metadata
        poem_details = scrape_poem(full_poem_url)
        
        # Only save the poem if we successfully extracted verses. If the page 
        # was malformed or empty, we skip it to avoid saving useless JSON files.
        if poem_details and poem_details["verses"]:
            # Construct the final, structured JSON payload mapping all the collected data
            poem_data = {
                "era": era_name,
                "poet": poet_name,
                "poem_title": poem_title,
                "diwan": poem_details["diwan"],
                "bahr": poem_details["bahr"],
                "qafiyah": poem_details["qafiyah"],
                "source_url": full_poem_url,
                "verses": poem_details["verses"]
            }
            
            # Save the file. ensure_ascii=False is required so Arabic text isn't saved as \u0627 Unicode hashes.
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(poem_data, f, ensure_ascii=False, indent=4)
                
        # Delay to avoid rate-limiting
        time.sleep(1) 
            
    print(f"  [+] Completed {fix_ar(poet_name)}.\n")

def main():
    """
    The main function orchestrates the entire crawling process. It starts by 
    collecting all the top-level eras, then iterates through each era to find its 
    poets, and finally scrapes each poet's poems.
    """
    print("--- Starting Al Diwan Full Crawl ---\n")
    
    # Collect top-level categories
    eras = get_eras()
    
    # Iterate through every era found
    for era in eras:
        print(f"========================================")
        print(f" ERA: {fix_ar(era['name'])}")
        print(f"========================================")
        
        # Collect all poets inside the current era
        poets = get_poets_in_era(era['url'])
        print(f"[*] Found {len(poets)} poets in {fix_ar(era['name'])}.\n")
        
        # Iterate through the poets and begin scraping their libraries
        for poet in poets:
            scrape_poet(poet['url'], era['name'], poet['name'])
            time.sleep(1) # Short delay between poets to avoid rate-limiting

    print("\nFULL CRAWL COMPLETE!")

if __name__ == "__main__":
    main()