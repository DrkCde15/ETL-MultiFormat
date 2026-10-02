"""Minimal schema contracts per format (presence checks only)."""

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "csv": ["transaction_id", "account_id", "amount", "timestamp"],
    "json": ["transaction_id", "account_id", "amount"],
    "xml": ["customer_id", "full_name"],
    "logs": ["timestamp", "account", "type", "amount", "status"],
}
