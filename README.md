# RAG-DingDong — Academic Drive Search

A vectorless RAG chatbot that searches your Google Drive academic materials using BM25 PageIndex and answers questions with Google Gemini (free tier).

## How it works

1. Files from your Google Drive folder are downloaded and parsed **page by page**
2. Each page is indexed using **BM25** (no vector embeddings, no paid APIs)
3. When you ask a question, BM25 retrieves the most relevant pages
4. **Gemini 1.5 Flash** generates a grounded answer with citations

## Setup

### 1. Google Cloud Setup

1. Go to https://console.cloud.google.com and create a project
2. Enable **Google Drive API**
3. Go to **Credentials** → Create **OAuth 2.0 Client ID** (Web Application)
4. Add authorized redirect URI: `http://localhost:8000/auth/callback`
5. Download the credentials JSON → save as `backend/client_secret.json`

### 2. Gemini API Key (free)

1. Go to https://aistudio.google.com/apikey
2. Create an API key (same Google account, no credit card)
3. Copy the key

### 3. Configure environment

```
cp .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=your_key_here
DRIVE_FOLDER_ID=1R22isu0HXNka5aU3X9KYqDraW9esTeyW
```

### 4. Run

**Windows:**
```
run.bat
```

**Linux/Mac:**
```
chmod +x run.sh && ./run.sh
```

Then open http://localhost:8000

## Usage

1. Click **Login with Google** → authorize Drive access
2. Click **Build Index** → waits while your Drive is crawled (first time takes a few minutes)
3. Ask questions in the chat box
4. See answers with source document citations

## Free Tier Limits

- Gemini 1.5 Flash: 15 requests/minute, 1M tokens/day
- Google Drive API: no practical limit for personal use
