"""Primary key and foreign key rules, with no SDK calls, so they can be tested and run on a laptop.

A customer row's primary key is its `Id`, which Data Fabric assigns. An order's foreign key, the
field `Customer`, holds that `Id`. Callers know customers by their business key (`C001`), so an
order's customer code has to be turned into the customer's `Id` before the order can be written.
"""

from pydantic import BaseModel, Field


class Customer(BaseModel):
    customer_code: str = Field(min_length=1)  # the business key, unique; not the primary key
    customer_name: str = Field(min_length=1)


class Order(BaseModel):
    order_number: str = Field(min_length=1)
    customer_code: str = Field(min_length=1)  # which customer, by business key
    amount: float = Field(ge=0)


class CustomerSummary(BaseModel):
    customer_code: str
    customer_name: str
    order_count: int
    total_amount: float


def resolve_orders(orders: list[Order], customer_ids: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Order rows ready to insert, each pointing at its customer's Id, and the orders refused.

    `customer_ids` maps a customer code to that customer's Id. An order whose customer isn't in it
    is refused here, before Data Fabric sees it: the foreign key check is ours to make.
    """
    rows, rejected = [], []
    for order in orders:
        customer_id = customer_ids.get(order.customer_code)
        if customer_id is None:
            rejected.append(f"{order.order_number}: no customer {order.customer_code}")
            continue
        rows.append({"OrderNumber": order.order_number, "Customer": customer_id, "Amount": order.amount})
    return rows, rejected


def summarize(customer_rows: list[dict], order_rows: list[dict]) -> list[CustomerSummary]:
    """One line per customer with their order count and total, by joining on the foreign key.

    Every customer gets a line, those with no orders included: a LEFT JOIN, not an INNER JOIN.
    Sorted by customer code.
    """
    count: dict[str, int] = {}
    total: dict[str, float] = {}
    for order in order_rows:
        customer_id = order["Customer"]
        count[customer_id] = count.get(customer_id, 0) + 1
        total[customer_id] = total.get(customer_id, 0.0) + float(order["Amount"])
    return [
        CustomerSummary(
            customer_code=c["CustomerCode"],
            customer_name=c["CustomerName"],
            order_count=count.get(c["Id"], 0),
            total_amount=round(total.get(c["Id"], 0.0), 2),
        )
        for c in sorted(customer_rows, key=lambda c: c["CustomerCode"])
    ]


if __name__ == "__main__":
    # A laptop run with no Data Fabric: made-up Ids stand in for the ones Data Fabric assigns.
    # uv run python keys.py ../../data/customers.json ../../data/orders.json
    import json
    import sys

    customers = [Customer(**c) for c in json.load(open(sys.argv[1]))]
    orders = [Order(**o) for o in json.load(open(sys.argv[2]))]
    ids = {c.customer_code: f"id-of-{c.customer_code}" for c in customers}
    order_rows, rejected = resolve_orders(orders, ids)
    customer_rows = [
        {"Id": ids[c.customer_code], "CustomerCode": c.customer_code, "CustomerName": c.customer_name}
        for c in customers
    ]
    summary = [s.model_dump() for s in summarize(customer_rows, order_rows)]
    print(json.dumps({"order_rows": order_rows, "rejected": rejected, "summary": summary}, indent=2))
