import logging

from pydantic import BaseModel, Field, field_validator
from uipath.platform import UiPath
from uipath.platform.entities.entities import (
    EntityQueryFilter,
    EntityQueryFilterGroup,
    LogicalOperator,
    QueryFilterOperator,
)

from keys import Customer, CustomerSummary, Order, resolve_orders, summarize

logger = logging.getLogger(__name__)

CUSTOMER_ENTITY = "DatastoreSimCustomer"  # the one side: primary key Id, business key CustomerCode
ORDER_ENTITY = "DatastoreSimOrder"  # the many side: foreign key Customer

# A query returns at most 1,000 records. ponytail: reading stops after MAX_PAGES pages (50,000
# rows), and one customer lookup takes at most 1,000 codes. Split the codes if a batch ever has more.
PAGE_SIZE = 1000
MAX_PAGES = 50

_sdk: UiPath | None = None


def sdk() -> UiPath:
    # Created on first use, not at import: `uipath init` imports this file, and UiPath() needs a
    # login. Tests replace this function with a fake.
    global _sdk
    if _sdk is None:
        _sdk = UiPath()
    return _sdk


class DatastoreIn(BaseModel):
    operation: str  # "add_customers", "add_orders" or "orders_per_customer", fixed per Flow node
    customers: list[Customer] = Field(default_factory=list)  # add_customers
    orders: list[Order] = Field(default_factory=list)  # add_orders

    # A Flow node sends null for an input it doesn't set, and a list field refuses null.
    @field_validator("customers", "orders", mode="before")
    @classmethod
    def null_means_empty(cls, value):
        return [] if value is None else value


class DatastoreOut(BaseModel):
    ok: bool = True  # false when Data Fabric refused or failed something
    error_message: str = ""
    # add_customers:
    customers_added: int = 0
    customer_ids: dict[str, str] = Field(default_factory=dict)  # code -> the Id Data Fabric assigned
    customers_failed: list[str] = Field(default_factory=list)  # refused by Data Fabric
    # add_orders:
    orders_added: int = 0
    orders_rejected: list[str] = Field(default_factory=list)  # refused by our foreign key check
    orders_failed: list[str] = Field(default_factory=list)  # refused by Data Fabric
    # orders_per_customer:
    summary: list[CustomerSummary] = Field(default_factory=list)


def _key(entity_name: str) -> str:
    # Record calls take the entity's Id, which differs per tenant, so look it up by name.
    return str(sdk().entities.retrieve_by_name(entity_name).id)


def _row(record) -> dict:
    """An SDK record as a plain dict keyed by field name, with Customer as the bare Id."""
    row = record.model_dump(by_alias=True)
    customer = row.get("Customer")
    # UiPath's Data Fabric skill says a read echoes a relationship as the parent's Id. If a tenant
    # returns the parent row instead, keep only its Id.
    if isinstance(customer, dict):
        row["Customer"] = customer.get("Id")
    return row


def _all_rows(key: str) -> list[dict]:
    rows = []
    for page_number in range(MAX_PAGES):
        page = sdk().entities.retrieve_records(key, start=page_number * PAGE_SIZE, limit=PAGE_SIZE)
        rows += [_row(r) for r in page.items]
        if not page.has_next_page:
            return rows
    logger.warning("Stopped after %d pages; the result is partial", MAX_PAGES)
    return rows


def _customer_ids(codes: list[str]) -> dict[str, str]:
    """Customer code -> customer Id, in one query: WHERE CustomerCode IN (...)."""
    if not codes:
        return {}
    group = EntityQueryFilterGroup(
        logical_operator=LogicalOperator.And,
        query_filters=[
            EntityQueryFilter(field_name="CustomerCode", operator=QueryFilterOperator.In, value_list=codes)
        ],
    )
    page = sdk().entities.retrieve_records(_key(CUSTOMER_ENTITY), filter_group=group, start=0, limit=PAGE_SIZE)
    return {r["CustomerCode"]: r["Id"] for r in map(_row, page.items)}


def _errors(batch) -> list[str]:
    return [f.error or "unknown error" for f in batch.failure_records]


def _op_add_customers(input: DatastoreIn) -> DatastoreOut:
    """One row per customer, in one batch call. Data Fabric assigns each row's Id, the primary key."""
    rows = [{"CustomerCode": c.customer_code, "CustomerName": c.customer_name} for c in input.customers]
    if not rows:
        return DatastoreOut()
    try:
        batch = sdk().entities.insert_records(_key(CUSTOMER_ENTITY), rows)
    except Exception as e:
        logger.warning("Adding customers failed: %s", e)
        return DatastoreOut(ok=False, error_message=str(e))
    failed = _errors(batch)  # e.g. a second C001: CustomerCode is unique
    added = [_row(r) for r in batch.success_records]
    return DatastoreOut(
        ok=not failed,
        error_message="; ".join(failed),
        customers_added=len(added),
        customer_ids={r["CustomerCode"]: r["Id"] for r in added if "CustomerCode" in r},
        customers_failed=failed,
    )


def _op_add_orders(input: DatastoreIn) -> DatastoreOut:
    """Turn each order's customer code into that customer's Id, refuse unknown customers, then
    write the rest in one batch call."""
    try:
        ids = _customer_ids(sorted({o.customer_code for o in input.orders}))
        rows, rejected = resolve_orders(input.orders, ids)
        batch = sdk().entities.insert_records(_key(ORDER_ENTITY), rows) if rows else None
    except Exception as e:
        logger.warning("Adding orders failed: %s", e)
        return DatastoreOut(ok=False, error_message=str(e))
    failed = _errors(batch) if batch else []  # e.g. a second O1001: OrderNumber is unique
    return DatastoreOut(
        ok=not failed,
        error_message="; ".join(failed),
        orders_added=len(batch.success_records) if batch else 0,
        orders_rejected=rejected,
        orders_failed=failed,
    )


def _op_orders_per_customer(input: DatastoreIn) -> DatastoreOut:
    """Every customer with their order count and total: both tables read once, joined in Python on
    the foreign key. Customers with no orders are listed with 0."""
    try:
        customers = _all_rows(_key(CUSTOMER_ENTITY))
        orders = _all_rows(_key(ORDER_ENTITY))
    except Exception as e:
        logger.warning("Reading customers and orders failed: %s", e)
        return DatastoreOut(ok=False, error_message=str(e))
    return DatastoreOut(summary=summarize(customers, orders))


OPERATIONS = {
    "add_customers": _op_add_customers,
    "add_orders": _op_add_orders,
    "orders_per_customer": _op_orders_per_customer,
}


def main(input: DatastoreIn) -> DatastoreOut:
    handler = OPERATIONS.get(input.operation)
    if handler is None:
        raise ValueError(
            f"Unknown operation {input.operation!r}; expected one of: {', '.join(OPERATIONS)}"
        )
    output = handler(input)
    logger.info(
        "%s: ok=%s customers_added=%d orders_added=%d rejected=%d summary=%d",
        input.operation,
        output.ok,
        output.customers_added,
        output.orders_added,
        len(output.orders_rejected),
        len(output.summary),
    )
    return output
