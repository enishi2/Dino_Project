# Security Checklist

## Already enforced in this project

- Public tables use Row Level Security.
- `FORCE ROW LEVEL SECURITY` is enabled on:
  - `public.conversations`
  - `public.messages`
  - `public.blocks`
- `anon` has no direct table privileges.
- The frontend uses only:
  - `SUPABASE_ANON_KEY`
- The app does not use `service_role` in the frontend code.
- Policies protect:
  - `select`
  - `insert`
  - `update`
  - `delete`
- `messages` and `blocks` are protected through ownership of the parent conversation.
- Unique constraints prevent duplicate imports and duplicate positions inside a conversation.

## Manual checks to run in Supabase

### 1. Apply the latest schema

Run [supabase_schema.sql](</C:/Naydino Project/supabase_schema.sql>) again in the Supabase SQL editor.

### 2. Verify RLS is enabled

In Supabase Table Editor, confirm RLS is enabled for:

- `conversations`
- `messages`
- `blocks`

### 3. Cross-user isolation test

Create two users:

- User A
- User B

Test flow:

1. Sign in as User A.
2. Upload a WhatsApp export.
3. Confirm data appears in the app.
4. Sign out.
5. Sign in as User B.
6. Confirm User B cannot see User A's conversation in the app.
7. If you test through the API, try reading `conversations`, `messages`, and `blocks` using User B's session token.
8. Confirm User B gets only their own rows.

### 4. Tampering checks

Test these cases from the frontend or API client:

- Change `user_id` manually in a conversation insert.
- Try loading another user's `conversation_id`.
- Try inserting `messages` or `blocks` linked to another user's conversation.
- Try updating rows that belong to another user.
- Try deleting rows that belong to another user.

Expected result:

- The request must fail or return no rows.

### 5. Auth/session checks

Test these flows:

- invalid password
- logout
- expired token
- request without login
- optional: email confirmation flow
- optional: password reset flow

## Supabase dashboard settings to enable

These are configured in the Supabase dashboard, not in this repo:

- Email confirmation settings
- Password reset behavior
- Rate limits for auth endpoints
- Trusted redirect URLs only

## Do not do this

- Do not put `service_role` in Streamlit secrets exposed to frontend code paths.
- Do not ship `service_role` to the browser.
- Do not disable RLS on public tables.
