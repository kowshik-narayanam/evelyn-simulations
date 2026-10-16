import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from uipath.platform.entities.entities import (
    EntityRecord,
    EntityRecordsBatchResponse,
    FailureRecord,
    QueryFilterOperator,
    RetrieveEntityRecordsResponse,
)

import main
from keys import Order, resolve_orders
from main import DatastoreIn

HERE = Path(__file__).parent
SIMULATION = HERE.parent.parent  # Datastore Simulation/
CUSTOMERS = json.loads((SIMULATION / "data" / "customers.json").read_text())
ORDERS = json.loads((SIMULATION / "data" / "orders.json").read_text())

# What orders_per_customer returns for the two data files: every customer, sorted by code.
EXPECTED = [
    ("C001", "Gill Bates", 3, 200.50),  # O1001, O1003, O1007
    ("C002", "Melon Eusk", 1, 300.00),  # O1004
    ("C003", "Beff Jezos", 2, 57.10),  # O1002, O1006
    ("C004", "Alice Wonderland", 0, 0.0),  # no orders: still listed
    ("C005", "John Doe", 1, 5.25),  # O1008
]


class FakeEntities:
    """Stands in for sdk().entities: the two entities, their unique keys and the foreign key."""

    def __init__(self):
        self.ids = {"DatastoreSimCustomer": "customer-entity", "DatastoreSimOrder": "order-entity"}
        self.rows: dict[str, list[dict]] = {"customer-entity": [], "order-entity": []}
        self.calls: list[str] = []
        self.filters: list = []
        self.fail: Exception | None = None
        self.relationship_as_object = False  # read Customer back as {"Id": ...} instead of the Id

    def retrieve_by_name(self, name, folder_key=None):
        self.calls.append("retrieve_by_name")
        if self.fail:
            raise self.fail
        return SimpleNamespace(id=self.ids[name])

    def _new_id(self):
        n = sum(len(r) for r in self.rows.values()) + 1
        return f"00000000-0000-0000-0000-{n:012d}"  # Data Fabric assigns the primary key

    def insert_records(self, key, records, schema=None, expansion_level=None, fail_on_first=None):
        self.calls.append("insert_records")
        unique = {"customer-entity": "CustomerCode", "order-entity": "OrderNumber"}[key]
        ok, failed = [], []
        for data in records:
            if key == "order-entity":
                customer_ids = {c["Id"] for c in self.rows["customer-entity"]}
                assert data["Customer"] in customer_ids, "an order must hold a customer's Id"
            if any(r[unique] == data[unique] for r in self.rows[key]):
                failed.append(FailureRecord(error=f"{data[unique]}: {unique} must be unique", record=data))
                continue
            row = {"Id": self._new_id(), **data}
            self.rows[key].append(row)
            ok.append(EntityRecord(**row))
        return EntityRecordsBatchResponse(successRecords=ok, failureRecords=failed)

    def retrieve_records(self, key, filter_group=None, start=None, limit=None, **unused):
        self.calls.append("retrieve_records")
        rows = self.rows[key]
        if filter_group:
            (f,) = filter_group.query_filters
            self.filters.append(f)
            assert f.operator == QueryFilterOperator.In
            rows = [r for r in rows if r[f.field_name] in f.value_list]
        page = rows[start : start + limit]
        if self.relationship_as_object:
            page = [{**r, "Customer": {"Id": r["Customer"]}} if "Customer" in r else r for r in page]
        return RetrieveEntityRecordsResponse(
            items=[EntityRecord(**r) for r in page],
            totalCount=len(rows),
            hasNextPage=start + len(page) < len(rows),
        )


@pytest.fixture
def fake(monkeypatch):
    entities = FakeEntities()
    monkeypatch.setattr(main, "sdk", lambda: SimpleNamespace(entities=entities))
    return entities


def run(operation, **inputs):
    return main.main(DatastoreIn(operation=operation, **inputs))


def run_the_flow():
    # The three nodes, in the Flow's order.
    return (
        run("add_customers", customers=CUSTOMERS),
        run("add_orders", orders=ORDERS),
        run("orders_per_customer"),
    )


def as_tuples(summary):
    return [(s.customer_code, s.customer_name, s.order_count, s.total_amount) for s in summary]


def test_the_data_has_a_customer_with_no_orders_and_an_order_with_no_customer():
    customer_codes = {c["customer_code"] for c in CUSTOMERS}
    order_codes = {o["customer_code"] for o in ORDERS}
    assert customer_codes - order_codes == {"C004"}
    assert order_codes - customer_codes == {"C999"}


def test_add_customers_writes_one_row_each_and_returns_the_ids_data_fabric_assigned(fake):
    output = run("add_customers", customers=CUSTOMERS)
    assert output.ok and output.customers_added == 5
    assert output.customer_ids == {r["CustomerCode"]: r["Id"] for r in fake.rows["customer-entity"]}
    assert fake.calls == ["retrieve_by_name", "insert_records"]  # one batch for all five


def test_a_second_c001_is_refused_by_the_unique_business_key(fake):
    run("add_customers", customers=CUSTOMERS)
    output = run("add_customers", customers=CUSTOMERS[:1])
    assert not output.ok and output.customers_added == 0
    assert output.customers_failed == ["C001: CustomerCode must be unique"]


def test_an_order_stores_its_customers_id_not_the_code(fake):
    customer_ids = run("add_customers", customers=CUSTOMERS).customer_ids
    output = run("add_orders", orders=ORDERS)
    assert output.ok and output.orders_added == 7
    by_number = {o["OrderNumber"]: o for o in fake.rows["order-entity"]}
    assert by_number["O1001"]["Customer"] == customer_ids["C001"]
    assert by_number["O1004"]["Customer"] == customer_ids["C002"]
    assert by_number["O1008"]["Customer"] == customer_ids["C005"]


def test_an_order_for_an_unknown_customer_is_rejected_before_data_fabric_sees_it(fake):
    run("add_customers", customers=CUSTOMERS)
    output = run("add_orders", orders=ORDERS)
    assert output.orders_rejected == ["O1005: no customer C999"]
    assert "O1005" not in {o["OrderNumber"] for o in fake.rows["order-entity"]}


def test_the_customer_lookup_is_one_query_with_in(fake):
    run("add_customers", customers=CUSTOMERS)
    fake.calls.clear()
    run("add_orders", orders=ORDERS)
    (f,) = fake.filters
    assert f.field_name == "CustomerCode" and f.value_list == ["C001", "C002", "C003", "C005", "C999"]
    # The order entity's name, the customer entity's name, one query, one batch.
    assert sorted(fake.calls) == sorted(["retrieve_by_name"] * 2 + ["retrieve_records", "insert_records"])


def test_every_customer_is_listed_including_one_with_no_orders(fake):
    *_, summary = run_the_flow()
    assert summary.ok and as_tuples(summary.summary) == EXPECTED


def test_the_summary_reads_every_page(fake, monkeypatch):
    run_the_flow()
    monkeypatch.setattr(main, "PAGE_SIZE", 2)
    assert as_tuples(run("orders_per_customer").summary) == EXPECTED


def test_a_relationship_read_back_as_the_parent_row_still_joins(fake):
    run("add_customers", customers=CUSTOMERS)
    run("add_orders", orders=ORDERS)
    fake.relationship_as_object = True
    assert as_tuples(run("orders_per_customer").summary) == EXPECTED


def test_running_the_flow_twice_adds_nothing_the_second_time(fake):
    run_the_flow()
    customers, orders, summary = run_the_flow()
    assert customers.customers_added == 0 and len(customers.customers_failed) == 5
    assert orders.orders_added == 0 and len(orders.orders_failed) == 7
    assert orders.orders_rejected == ["O1005: no customer C999"]
    assert as_tuples(summary.summary) == EXPECTED  # unchanged


def test_resolve_orders_refuses_every_order_when_there_are_no_customers():
    rows, rejected = resolve_orders([Order(**o) for o in ORDERS], {})
    assert rows == [] and len(rejected) == 8


def test_an_order_with_a_negative_amount_fails_at_the_contract():
    with pytest.raises(ValueError):
        DatastoreIn(operation="add_orders", orders=[{"order_number": "O1", "customer_code": "C001", "amount": -1}])


def test_null_inputs_from_the_flow_mean_empty(fake):
    output = main.main(DatastoreIn(operation="add_customers", customers=None, orders=None))
    assert output.ok and output.customers_added == 0 and fake.calls == []


@pytest.mark.parametrize(
    "operation, log",
    [
        ("add_customers", "Adding customers failed"),
        ("add_orders", "Adding orders failed"),
        ("orders_per_customer", "Reading customers and orders failed"),
    ],
)
def test_a_data_fabric_failure_is_logged_not_raised(fake, caplog, operation, log):
    fake.fail = ConnectionError("Data Fabric unreachable")
    with caplog.at_level(logging.WARNING):
        output = run(operation, customers=CUSTOMERS, orders=ORDERS)
    assert not output.ok and output.error_message == "Data Fabric unreachable"
    assert log in caplog.text


def test_the_code_writes_exactly_the_entity_files_fields(fake):
    run_the_flow()
    for entity, file in (("customer-entity", "DatastoreSimCustomer"), ("order-entity", "DatastoreSimOrder")):
        fields = {f["name"] for f in json.loads((SIMULATION / "entities" / f"{file}.create.json").read_text())["fields"]}
        written = {k for row in fake.rows[entity] for k in row if k != "Id"}
        assert written == fields, file


def test_an_unknown_operation_fails():
    with pytest.raises(ValueError, match="Unknown operation"):
        run("purge")
