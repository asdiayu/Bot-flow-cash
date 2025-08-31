-- Migration to add the 'category' column to the transactions table.
-- Run this script once in your Supabase SQL Editor.

ALTER TABLE public.transactions
ADD COLUMN category TEXT;
