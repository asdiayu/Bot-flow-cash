-- RPC function to calculate a user's total balance efficiently on the server.
-- Run this script once in your Supabase SQL Editor.

CREATE OR REPLACE FUNCTION calculate_balance(p_user_id bigint)
RETURNS numeric AS $$
DECLARE
    balance numeric;
BEGIN
    SELECT
       -- Sum up all income, treat null as 0
       COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) -
       -- Subtract the sum of all expenses, treat null as 0
       COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0)
    INTO
       balance
    FROM
       transactions
    WHERE
       user_id = p_user_id;

    RETURN balance;
END;
$$ LANGUAGE plpgsql;
