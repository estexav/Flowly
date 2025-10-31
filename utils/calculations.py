def calculate_transaction_summary(transactions):
    total_income = 0.0
    total_expenses = 0.0

    for transaction in transactions:
        amount = transaction.get('amount', 0.0)
        transaction_type = transaction.get('type')
        if transaction_type == 'Ingreso':
            total_income += amount
        elif transaction_type == 'Gasto':
            total_expenses += amount

    total_balance = total_income - total_expenses
    return total_income, total_expenses, total_balance