# Supabase → Backend Email Hooks (Tasks INSERT/UPDATE)

This backend already exposes email notification endpoints under:

- `POST /notifications/email/intern-new-task`
- `POST /notifications/email/mentor-update`

This addition provides a **single** Supabase Database Webhook endpoint that can be called on `tasks` table changes:

- `POST /hooks/supabase/tasks`

It securely triggers the existing email routes server-side, keeping `RESEND_API_KEY` hidden from the frontend.

## Environment Variables

Add this **server-side only** env var to the backend container:

- `SUPABASE_HOOK_SECRET` = a long random secret used to authenticate Supabase webhook calls.

The webhook must pass it in either:

- Header `x-supabase-hook-secret: <SUPABASE_HOOK_SECRET>`  
  or
- `Authorization: Bearer <SUPABASE_HOOK_SECRET>`

## Supabase Configuration (Database Webhooks)

In Supabase Dashboard:

1. Go to **Database → Webhooks** (or **Integrations → Database Webhooks**, depending on UI).
2. Create a webhook for the `tasks` table:
   - **Events**: `INSERT`, `UPDATE`
   - **URL**: `<YOUR_BACKEND_BASE_URL>/hooks/supabase/tasks`
   - **HTTP Method**: `POST`
   - **Headers**:
     - `x-supabase-hook-secret: <SUPABASE_HOOK_SECRET>`

### Required payload fields / assumptions

The handler expects the webhook payload to include `record` and (ideally) `old_record`.

It extracts these fields from the `record` object (best effort):

- `intern_id` (fallbacks: `owner_id` or `user_id`)
- `mentor_id`
- `task_title` (fallbacks: `title` or `name`)
- `created_at` (INSERT only; optional)
- `status` (UPDATE)
- `mentor_remarks` (fallback: `remarks`) (UPDATE)
- `meeting_datetime` (fallbacks: `meeting_time` / `meeting_at`) (UPDATE)

If your `tasks` schema uses different column names, update the extraction logic in:
`src/api/routers/supabase_hooks.py` (`_extract_task_fields()`).

## Trigger behavior

### INSERT on `tasks`
Calls `POST /notifications/email/intern-new-task` with:
- `intern_id`, `mentor_id`, `task_title`, `created_at`

### UPDATE on `tasks`
Calls `POST /notifications/email/mentor-update` **only when one of these fields changes**:
- `status`
- `mentor_remarks` / `remarks`
- `meeting_datetime` / `meeting_time`

If the webhook payload does not include `old_record`, the handler conservatively triggers on UPDATE.

## Notes

- This is intentionally implemented as a webhook endpoint (HTTP), because Supabase database triggers/functions cannot directly call external HTTP endpoints without extra extensions. Database Webhooks are the intended mechanism for “DB event → HTTP call”.
- The backend still fetches recipient emails dynamically from the `profiles` table using `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
