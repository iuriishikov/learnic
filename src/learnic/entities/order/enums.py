from enum import StrEnum


class OrderStatus(StrEnum):
    PAID = "paid"
    REFUNDED = "refunded"
