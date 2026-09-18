import time
import json
import pandas as pd
from openai import OpenAI
from bs4 import BeautifulSoup, Comment
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. GLOBAL CONFIGURATION ---
# GET KEY: https://build.nvidia.com/
NVIDIA_API_KEY = ""  # PASTE YOUR KEY HERE

MAX_PAGES = 10 
TARGET_URLS = [
"https://medicine.nus.edu.sg/dbmi/about-us/faculty/"
]

# --- 2. SETUP AI (NVIDIA NIM) ---
print("⚙️ Configuring AI (NVIDIA Llama 3.1 405B)...")
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# We use the 405B model because analyzing HTML requires high intelligence
MODEL_NAME = "deepseek-ai/deepseek-v3.2"

# --- 3. HELPER FUNCTIONS ---
def clean_html_for_ai(raw_html):
    """Strips junk to make HTML lighter for the AI."""
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["script", "style", "svg", "path", "noscript", "footer", "header", "nav", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    # 405B has 128k context, so 60k chars is safe
    return str(soup)[:60000]

def find_smart_next_button(driver, ai_selector=None):
    """Tries AI selector first, then generic 'Next' patterns."""
    if ai_selector:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, ai_selector)
            visible = [b for b in buttons if b.is_displayed()]
            if visible:
                print(f"      🎯 Found Next button using AI Selector")
                return visible[0]
        except: pass

    print("      🔍 AI selector failed/missing. Trying generic 'Next' patterns...")
    xpaths = [
        "//a[contains(text(), 'Next')]", 
        "//a[contains(text(), 'next')]",
        "//a[contains(text(), '›')]",
        "//li[contains(@class, 'next')]/a",
        "//a[@rel='next']"
    ]
    for xpath in xpaths:
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
            visible = [b for b in buttons if b.is_displayed()]
            if visible:
                print(f"      🎯 Found Next button using Pattern: {xpath}")
                return visible[0]
        except: continue
    return None

# --- 4. CORE LOGIC: AI CONFIG ---
def get_ai_config(driver, url):
    print(f"\n🤖 [AI] Analyzing page structure...")
    
    if driver.current_url != url:
        driver.get(url)
        time.sleep(5) 
    
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    
    raw_html = driver.page_source
    cleaned_html = clean_html_for_ai(raw_html)

    prompt = f"""
    Analyze this HTML from a faculty directory. Return a JSON configuration object.
    
    Required Fields:
    1. "container": CSS selector for the repeating element (ONE faculty member card).
    2. "next": CSS selector for the "Next Page" button (null if none).
    3. "selectors": A nested object with exactly two fields:
       - "name": Selector for the professor's name text.
       - "profile": Selector for the link (href) to their individual bio/research page.
         * HINT: This is usually the <a> tag wrapping the Name, or a "Read More" / "View Profile" button.
         * WARNING: Do NOT select "mailto:" links.
    
    Rules:
    - Selectors must be RELATIVE to the "container".
    - Output ONLY valid JSON.
    - Look for trends like people's names in order to identify the correct selectors.
    
    HTML Snippet:
    {cleaned_html}
    """
    
    # NVIDIA limits: 40 requests/min. 
    # Since we are doing 1 request per site, a simple loop is fine.
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
                
            config_data = json.loads(content)
            
            return {
                "name": url.split("//")[1].split("/")[0],
                "selectors": {
                    "faculty": config_data["container"],
                    "next": config_data.get("next"),
                    **config_data["selectors"]
                }
            }
        except Exception as e:
            print(f"      ⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(2)
            
    return None

# --- 5. CORE LOGIC: SCRAPER ---
def scrape_with_config(driver, config):
    print(f"🚜 [Scraper] Extracting data...")
    all_rows = []
    page_count = 1
    
    while page_count <= MAX_PAGES:
        print(f"   📄 Page {page_count}...")
        
        try:
            items = driver.find_elements(By.CSS_SELECTOR, config["selectors"]["faculty"])
            if len(items) == 0:
                time.sleep(3)
                items = driver.find_elements(By.CSS_SELECTOR, config["selectors"]["faculty"])
        except:
            items = []

        print(f"      Found {len(items)} items.")

        for f in items:
            def get_val(key, attr="textContent"):
                css = config["selectors"].get(key)
                if not css: return ""
                try: 
                    elm = f.find_element(By.CSS_SELECTOR, css)
                    return elm.get_attribute(attr).strip()
                except: return ""

            row = {
                "university": config["name"],
                "name": get_val("name"),
                "profile": get_val("profile", "href")
            }
            
            if row["name"] and row["profile"]:
                all_rows.append(row)

        # Pagination Logic
        ai_selector = config["selectors"].get("next")
        next_btn = find_smart_next_button(driver, ai_selector)
        
        if not next_btn:
            print("      🛑 No 'Next' button found. Finished.")
            break
        
        try:
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(5)
            page_count += 1
        except Exception as e:
            print(f"      ⚠️ Pagination error: {e}")
            break

    return all_rows

# --- 6. MAIN PIPELINE ---
def run_pipeline():
    print("🚀 Launching Chrome...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    master_data = []

    try:
        for url in TARGET_URLS:
            print(f"\n--- Processing: {url} ---")
            
            config = get_ai_config(driver, url)
            
            if not config:
                print("   ⚠️ Skipping: AI failed to generate config.")
                continue
                
            container = config['selectors'].get('faculty')
            if not container:
                print(f"   ⚠️ Skipping: AI could not find the container element on {url}")
                continue

            print(f"   ✅ AI Config Valid. Container: {container}")

            try:
                data = scrape_with_config(driver, config)
                master_data.extend(data)
                print(f"   ✅ Extracted {len(data)} rows.")
            except Exception as e:
                print(f"   ❌ Scraper Error: {e}")
            
            # NVIDIA Rate Limit Safety (40 RPM = ~1.5s per req)
            time.sleep(2) 

    finally:
        print("\n🛑 Closing Browser...")
        driver.quit()

    if master_data:
        df = pd.DataFrame(master_data)
        df.to_csv("faculty_links_output.csv", index=False)
        print("\n🎉 DONE! Saved 'faculty_links_output.csv'")
        print(df.head())
    else:
        print("\n❌ No data extracted.")

if __name__ == "__main__":
    run_pipeline()
    input("\nPress Enter to exit...")