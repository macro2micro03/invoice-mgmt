from datetime import date
from types import SimpleNamespace

from app import report_from_records


def _invoice(spec, vendor, weight, note="", delivery_date=None):
    return SimpleNamespace(spec=spec, vendor=vendor, weight=weight, note=note, delivery_date=delivery_date)


def test_build_report_data_from_invoices_separates_rows_by_spec_and_vendor():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, "동국제강"),
        _invoice("SHD10", "대한제강", 0.5, "한영철강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert len(data["specs"]) == 2
    specs_by_vendor = {s["vendor"]: s for s in data["specs"]}
    assert specs_by_vendor["동경강업(주)/동국제강"]["quantity_ton"] == 1.0
    assert specs_by_vendor["대한제강/한영철강"]["quantity_ton"] == 0.5


def test_build_report_data_from_invoices_merges_same_spec_and_vendor_summing_weight_and_joining_notes():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, "동국제강"),
        _invoice("SHD10", "동경강업(주)", 0.5, "한영철강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert len(data["specs"]) == 1
    assert data["specs"][0]["vendor"] == "동경강업(주)/동국제강, 한영철강"
    assert data["specs"][0]["quantity_ton"] == 1.5


def test_build_report_data_from_invoices_does_not_duplicate_repeated_notes():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, "동국제강"),
        _invoice("SHD10", "동경강업(주)", 0.5, "동국제강"),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert data["specs"][0]["vendor"] == "동경강업(주)/동국제강"
    assert data["specs"][0]["quantity_ton"] == 1.5


def test_build_report_data_from_invoices_summary_vendor_lists_all_rows_comma_separated():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, "동국제강"),
        _invoice("SHD13", "대한제강", 0.5, ""),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices, delivery_date="2026-04-20")
    assert data["vendor"] == "동경강업(주)/동국제강, 대한제강"


def test_build_report_data_from_invoices_sets_delivery_date_and_empty_skipped_pages():
    data = report_from_records.build_report_data_from_invoices([], delivery_date="2026-04-20")
    assert data["delivery_date"] == "2026-04-20"
    assert data["skipped_pages"] == []
    assert data["specs"] == []
    assert data["vendor"] == ""


def test_build_report_data_from_invoices_derives_delivery_date_when_not_given():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, delivery_date=date(2026, 4, 20)),
        _invoice("SHD13", "대한제강", 0.5, delivery_date=date(2026, 4, 20)),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices)
    assert data["delivery_date"] == "2026-04-20"


def test_build_report_data_from_invoices_joins_distinct_dates_when_not_given():
    invoices = [
        _invoice("SHD10", "동경강업(주)", 1.0, delivery_date=date(2026, 4, 20)),
        _invoice("SHD13", "대한제강", 0.5, delivery_date=date(2026, 4, 21)),
    ]
    data = report_from_records.build_report_data_from_invoices(invoices)
    assert data["delivery_date"] == "2026-04-20, 2026-04-21"
