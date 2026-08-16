-- Treasure Coast Today subscriber chrome personalization.
-- Stores only the subscriber first name needed for signed-in header presentation.

alter table public.profiles
  add column if not exists first_name text;
