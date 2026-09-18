import time
import json
import re
import pandas as pd
from openai import OpenAI
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
from difflib import SequenceMatcher

# --- CONFIGURATION ---
NVIDIA_API_KEY = ""  # PASTE YOUR KEY HERE
INPUT_CSV = "faculty_links_output.csv"
OUTPUT_CSV = "final_shortlist_nvidia.csv"

# --- 1. MODEL SETUP (NVIDIA) ---
print("⚙️ Configuring AI (NVIDIA Llama 3.3 70B)...")
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# Llama 3.3 70B is the perfect balance of Speed vs Intelligence
MODEL_NAME = "deepseek-ai/deepseek-v3.1-terminus"

# --- 2. KEYWORDS ---
KEYWORD_GROUPS = {
    "AI/ML": ["deep learning", "machine learning", "neural network", "computer vision", "artificial intelligence", "cnn", "rnn", "transformer", "data driven"],
    "Imaging": ["mri", "ct scan", "ultrasound", "microscopy", "optical coherence", "tomography", "medical imaging", "image analysis", "computational"],
    "Biomechanics": ["biomechanics", "gait", "locomotion", "kinematics", "musculoskeletal", "tissue mechanics", "prosthetics", "orthotics"],
    "Wearables/Sensors": ["wearable", "sensor", "imu", "monitoring", "biosensor", "flexible electronics", "iot"],
    "Neuro": ["neuroengineering", "brain-computer", "bci", "neural interface", "neuromodulation", "eeg", "emg"],
    "Rehab": ["rehabilitation", "assistive technology", "exoskeleton", "haptics", "robotic therapy"]
}

INTERESTS_DESCRIPTION = """
Bioinstrumentation, Biomedical Imaging, Deep Learning/ML in Healthcare, 
Biomechanics, Wearable Systems, Neuroengineering, Rehabilitation.
"""

# --- HELPER: EMAIL INTELLIGENCE ---
def get_best_email(text, professor_name, university_url):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    obfuscated_pattern = r'([a-zA-Z0-9._%+-]+)\s*(?:\[at\]|at|@)\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|dot|\.)\s*([a-zA-Z]{2,})'
    
    raw_emails = re.findall(email_pattern, text)
    hidden_matches = re.findall(obfuscated_pattern, text, re.IGNORECASE)
    cleaned_hidden = [f"{m[0]}@{m[1]}.{m[2]}" for m in hidden_matches]
    
    all_emails = list(set(raw_emails + cleaned_hidden))
    
    ignore_list = ["wix", "domain", "example", "sentry", "wixpress", "email", "contact", "jpg", "png"]
    candidates = [e for e in all_emails if not any(x in e for x in ignore_list)]
    
    if not candidates: return None

    best_email = None
    highest_score = -1
    
    prof_name_clean = re.sub(r'[^a-zA-Z]', '', professor_name.lower())
    prof_parts = professor_name.lower().split()
    
    try: uni_domain = urlparse(university_url).netloc.replace("www.", "").split('.')[-2]
    except: uni_domain = ""

    for email in candidates:
        score = 0
        local_part = email.split('@')[0].lower()
        domain_part = email.split('@')[1].lower()
        
        # Scoring Rules
        if uni_domain and uni_domain in domain_part: score += 50
        for part in prof_parts:
            if len(part) > 2 and part in local_part: score += 20
        
        similarity = SequenceMatcher(None, local_part, prof_name_clean).ratio()
        score += (similarity * 30)
        
        if local_part in ["info", "admin", "webmaster", "jobs", "lab", "contact"]: score -= 50

        if score > highest_score:
            highest_score = score
            best_email = email
            
    return best_email

# --- HELPER: TEXT EXTRACTION ---
def check_keywords_python(text):
    text_lower = text.lower()
    found = []
    for category, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(f"{category}: {kw}")
                break 
    return (len(found) > 0), found

def get_clean_text(driver, url):
    if pd.isna(url) or "http" not in str(url): return None
    try:
        driver.get(url)
        time.sleep(1.5)
        soup = BeautifulSoup(driver.page_source, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "svg"]):
            tag.decompose()
        # Truncate for efficiency (Llama 3 context is large but let's be fast)
        return soup.get_text(separator=' ', strip=True)[:15000]
    except: return None

# --- HELPER: AI ANALYSIS ---
# --- HELPER: AI ANALYSIS (ROBUST) ---
def analyze_with_nvidia(name, text, keywords):
    prompt = f"""
    You are a data filtering assistant. 
    Student Interests: {INTERESTS_DESCRIPTION}
    
    Professor: {name}
    Keywords Found: {', '.join(keywords)}
    Profile Snippet: \"\"\"{text[:6000]}\"\"\"
    
    Task:
    1. Decide if this is a research match (True/False).
    2. Extract their Last Name.
    3. Write a short reason.
    4. Assign a relevance score (0-100).
    
    CRITICAL INSTRUCTION: Return ONLY a raw JSON object. Do NOT include markdown formatting.
    
    Example Output:
    {{ "is_match": true, "score": 85, "reason": "Focuses on neural interfaces.", "last_name": "Smith" }}
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a machine that outputs strict JSON only."}, 
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        
        # Robust Cleaner
        start_index = content.find('{')
        end_index = content.rfind('}')
        
        if start_index != -1 and end_index != -1:
            json_str = content[start_index : end_index + 1]
            data = json.loads(json_str)
            
            # --- SAFETY CHECK ---
            # Ensure keys exist, set defaults if missing
            if 'is_match' not in data: data['is_match'] = False
            if 'score' not in data: data['score'] = 0
            if 'reason' not in data: data['reason'] = "No reason provided"
            if 'last_name' not in data: data['last_name'] = name.split()[-1]
            
            return data
        else:
            return None
            
    except Exception as e:
        print(f"      ⚠️ NVIDIA Error: {e}")
        return None

# --- MAIN ---
def run_smart_filter():
    try:
        df = pd.read_csv(INPUT_CSV)
    except:
        print("❌ Input CSV not found.")
        return

    print("🚀 Launching Chrome...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    
    matches = []
    
    try:
        for index, row in df.iterrows():
            name = row['name']
            url = row['profile']
            print(f"\n[{index+1}/{len(df)}] Scanning: {name}")
                
            text = get_clean_text(driver, url)
            if not text:
                print("   ⚠️ Dead link.")
                continue
            
            #if index == 0:
                print("⏳ First run complete. Waiting 200 seconds before continuing...")
                time.sleep(200)

            # 1. Email Extraction
            best_email = get_best_email(text, name, url)
            if best_email:
                print(f"   📧 Email Identified: {best_email}")
                row['email'] = best_email
            else:
                print("   ⚪ No personal email found.")
            
            # 2. Keyword Check
            passed_gate, keywords_found = check_keywords_python(text)
            if not passed_gate:
                print("   ❌ No keywords found.")
                #time.sleep(1000)
                continue
            
            # 3. NVIDIA AI Analysis
            print(f"   ✅ Keywords: {keywords_found}. Asking Llama...")
            ai_result = analyze_with_nvidia(name, text, keywords_found)
            
            # Check if result exists AND is a match
            if ai_result and ai_result.get('is_match'):
                # --- SAFELY GET VALUES USING .get() ---
                score = ai_result.get('score', 0)
                last_name = ai_result.get('last_name', name.split()[-1])
                
                print(f"   🔥 MATCH! ({score}/100) - Last Name: {last_name}")
                
                row['match_score'] = score
                row['keywords'] = ", ".join(keywords_found)
                row['match_reason'] = ai_result.get('reason', '')
                row['last_name'] = last_name
                
                matches.append(row)
                pd.DataFrame(matches).to_csv(OUTPUT_CSV, index=False)
            else:
                print("   📉 AI rejected.")

            # Rate Limit Safety
            time.sleep(2)

    finally:
        driver.quit()
        print(f"\n🎉 Done! Curated list saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    run_smart_filter()
