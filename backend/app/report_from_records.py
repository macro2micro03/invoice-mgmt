def build_report_data_from_invoices(invoices, delivery_date: str) -> dict:
    groups: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []

    for invoice in invoices:
        key = (invoice.spec or "", invoice.vendor or "")
        if key not in groups:
            groups[key] = {"weight_ton": 0.0, "notes": []}
            order.append(key)
        groups[key]["weight_ton"] += invoice.weight or 0.0
        if invoice.note and invoice.note not in groups[key]["notes"]:
            groups[key]["notes"].append(invoice.note)

    specs = []
    vendor_displays = []
    for spec, vendor in order:
        data = groups[(spec, vendor)]
        notes_joined = ", ".join(data["notes"])
        vendor_display = f"{vendor}/{notes_joined}" if vendor and notes_joined else vendor
        specs.append(
            {
                "spec": spec,
                # Invoice.weight는 Ton 단위로 저장한다(기존 계약) — 변환 없이 그대로 합산한다.
                "quantity_ton": round(data["weight_ton"], 3),
                "vendor": vendor_display,
            }
        )
        vendor_displays.append(vendor_display)

    return {
        "specs": specs,
        "vendor": ", ".join(dict.fromkeys(v for v in vendor_displays if v)),
        "skipped_pages": [],
        "skipped_rows": 0,
        "delivery_date": delivery_date,
    }
