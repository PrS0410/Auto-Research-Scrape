# Automated-LLM-API-Research-Outreach-Pipeline
An end-to-end automation pipeline built to discover, evaluate, and contact university faculty for research opportunities.
## Pipeline Architecture

1. **Dynamic Web Scraper (`1_dynamic_scraper.py`)**
   Uses Selenium and BeautifulSoup to navigate university directories. Integrates LLM prompts to autonomously identify CSS container selectors and handle varying pagination structures.
2. **AI Filtering Engine (`2_ai_filtering_engine.py`)**
   Utilizes NVIDIA NIM APIs (Llama 3 / DeepSeek) to score profile alignment via zero-shot classification based on biomedical engineering keywords. Extracts obfuscated emails using custom Regex and SequenceMatcher algorithms.
3. **Automated Dispatch (`3_apps_script_mailer.js`)**
   A Google Apps Script that ingests the final curated CSV to automatically dispatch customized emails with dynamically attached resumes.

## Tech Stack
* **Python:** Selenium, BeautifulSoup4, Pandas, Regex
* **AI/ML:** NVIDIA NIM APIs (Llama 3.3 70B, DeepSeek)
* **Automation:** Google Apps Script

## Local Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Rename `.env.example` to `.env` and add your `NVIDIA_API_KEY`.
4. Run `python 1_dynamic_scraper.py` followed by `python 2_ai_filtering_engine.py`.
