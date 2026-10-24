`net_by_account` in `transactions.py` overwrites earlier amounts. Two transactions of 10 and -2.5 on account `a` give `-2.5` instead of `7.5`.
