# Dino Memo

Live app: https://dinoproject.streamlit.app/

Dino Memo is a web app for exploring WhatsApp conversations with AI-powered chat, timeline navigation, search, and mini-games like Guess Who Said It.

## Features

- AI chat over WhatsApp exports
- Timeline and semantic search
- Guess Who Said It mini-game
- Supabase email/password login
- Groq with Gemini fallback

## Run locally

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Set environment variables:

```powershell
$env:GROQ_API_KEY="your_groq_key"
$env:GEMINI_API_KEY="your_gemini_key"
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_ANON_KEY="your_supabase_anon_key"
```

Start the app:

```powershell
py -m streamlit run streamlit_app.py
```

If Supabase variables are not set, the app runs in local mode.

## Supabase setup

- Create a Supabase project
- Run `supabase_schema.sql` in SQL Editor
- Enable Email auth in Authentication > Providers
- Use the project URL without `/rest/v1`
- Use the `anon public` key, not `service_role`

## Deploy

For Streamlit Community Cloud:

- push the repo to GitHub
- set the main file to `streamlit_app.py`
- add these secrets:

```toml
GROQ_API_KEY = "your_groq_key"
GEMINI_API_KEY = "your_gemini_key"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

## Notes

- Keep API keys server-side only
- Do not use the Supabase `service_role` key in the app
- AI relationship analysis should be treated as a hypothesis, not certainty
