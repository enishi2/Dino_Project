# Dino Memo

Dino Memo is a Streamlit app that turns exported WhatsApp conversations into a private searchable memory. Users can sign in, upload a WhatsApp `.txt` export, ask natural questions about the conversation, browse a timeline, and receive AI answers grounded in retrieved excerpts.

## Features

- Supabase email/password authentication.
- Per-user conversation storage with Row Level Security.
- WhatsApp `.txt` parsing with date, sender, and message extraction.
- Smart conversation excerpts built from message continuity.
- Lightweight semantic/hybrid search over the indexed conversation.
- Groq support with Gemini fallback.
- Local SQLite mode for development when Supabase is not configured.
- Timeline and direct search views.

## Project Files

- `streamlit_app.py` - main Streamlit app.
- `whatsapp_memory_core.py` - parser, search, AI provider calls, and local SQLite helpers.
- `supabase_store.py` - Supabase Auth and database access.
- `supabase_schema.sql` - database tables, indexes, grants, and RLS policies.
- `assets/dino-memo-logo.png` - app logo.
- `requirements.txt` - deployment dependencies.

## Local Setup

1. Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

2. Set server-side API keys:

```powershell
$env:GROQ_API_KEY="your_groq_key"
$env:GEMINI_API_KEY="your_gemini_key"
```

3. Optional: enable Supabase cloud mode:

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_ANON_KEY="your_supabase_anon_key"
```

4. Start the app:

```powershell
py -m streamlit run streamlit_app.py
```

If `SUPABASE_URL` and `SUPABASE_ANON_KEY` are not configured, the app runs in local SQLite mode.

## Supabase Setup

1. Create a Supabase project.
2. Open **SQL Editor**.
3. Run all SQL from `supabase_schema.sql`.
4. Go to **Authentication > Providers**.
5. Enable **Email** sign-in.
6. For quick testing, you can disable email confirmation. For production, use confirmed emails.
7. Copy your **Project URL** and **anon public key**.

Use only the project URL:

```text
https://your-project.supabase.co
```

Do not use the REST URL:

```text
https://your-project.supabase.co/rest/v1/
```

## Streamlit Community Cloud Deploy

1. Push this project to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Create a new app from the GitHub repository.
4. Set the main file path to:

```text
streamlit_app.py
```

5. Add these secrets in the Streamlit app settings:

```toml
GROQ_API_KEY = "your_groq_key"
GEMINI_API_KEY = "your_gemini_key"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

6. Deploy the app.
7. Create a test account in the app.
8. Upload a WhatsApp `.txt` export and ask a test question.

## Render Deploy

1. Push this project to GitHub.
2. Create a new Render Web Service.
3. Select the GitHub repository.
4. Use this build command:

```bash
pip install -r requirements.txt
```

5. Use this start command:

```bash
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

6. Add these environment variables:

```text
GROQ_API_KEY
GEMINI_API_KEY
SUPABASE_URL
SUPABASE_ANON_KEY
```

7. Deploy and test sign-in/upload/chat.

## Security Notes

- Never commit `.env` files or API keys.
- `GROQ_API_KEY` and `GEMINI_API_KEY` must stay server-side.
- Use Supabase Row Level Security to isolate each user's conversations.
- The Supabase anon key is safe to use in client apps only when RLS policies are correct.
- Do not use the Supabase `service_role` key in Streamlit.

## Import Behavior

Uploading a WhatsApp `.txt` export creates or replaces a conversation with the same source file name for the signed-in user.

## AI Notes

AI relationship analysis should be treated as conversation-based hypotheses, not certainty.
