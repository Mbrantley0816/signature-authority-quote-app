import io
import math
import uuid
from datetime import date, datetime

import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BUSINESS_NAME = "The Signature Authority"
LEGAL_NAME = "Brantley Enterprise Group LLC"
PHONE = "(478) 607-5828"
EMAIL = "signatureauthorityga@gmail.com"

SERVICE_PRICES = {
    "General Mobile Notary": 35.00,
    "Hospital, Jail & Facility": 45.00,
    "Real Estate & Loan Signing": 99.00,
}

LOCAL_TRAVEL_FEE = 15.00
LOCAL_RADIUS_MILES = 25.0
EXTRA_MILE_RATE = 0.75
AFTER_HOURS_FEE = 20.00
NOTARIAL_ACT_FEE = 2.00
DEPOSIT_RATE = 0.25

SAGE = "#6F8064"
DARK_SAGE = "#3F4D3B"
CREAM = "#FAF7EF"
GOLD = "#B58A3A"


st.set_page_config(
    page_title="The Signature Authority Quote Generator",
    page_icon="✍️",
    layout="centered",
)

st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {CREAM}; }}
        h1, h2, h3 {{ color: {DARK_SAGE}; }}
        .title-card {{
            padding: 1.5rem;
            border: 1px solid #d8cfbc;
            border-radius: 18px;
            background: white;
            text-align: center;
            box-shadow: 0 4px 16px rgba(63, 77, 59, 0.08);
            margin-bottom: 1rem;
        }}
        .price-box {{
            padding: 1rem;
            border-radius: 14px;
            background: white;
            border-left: 6px solid {GOLD};
            margin: .4rem 0;
        }}
        div.stButton > button, div.stDownloadButton > button {{
            background-color: {DARK_SAGE};
            color: white;
            border-radius: 10px;
            border: none;
            width: 100%;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


def currency(amount: float) -> str:
    return f"${amount:,.2f}"


def round_money(amount: float) -> float:
    return round(float(amount) + 1e-9, 2)


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def calculate_one_way_distance(destination: str) -> tuple[float, str]:
    origin = get_secret("HOME_ADDRESS")
    api_key = get_secret("GOOGLE_MAPS_API_KEY")

    if not origin:
        raise ValueError("Your private starting address has not been added to the app settings.")
    if not api_key:
        raise ValueError("Your Google Maps API key has not been added to the app settings.")

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }
    payload = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "en-US",
        "units": "IMPERIAL",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=20)
    if response.status_code != 200:
        message = response.json().get("error", {}).get("message", response.text)
        raise ValueError(f"Google Maps could not calculate the route: {message}")

    routes = response.json().get("routes", [])
    if not routes:
        raise ValueError("No driving route was found for that destination.")

    route = routes[0]
    miles = route["distanceMeters"] / 1609.344
    seconds = int(str(route.get("duration", "0s")).replace("s", ""))
    minutes = max(1, math.ceil(seconds / 60))
    duration = f"{minutes // 60} hr {minutes % 60} min" if minutes >= 60 else f"{minutes} min"
    return round(miles, 1), duration


def travel_fee_for(miles: float) -> tuple[float, float]:
    extra_miles = max(0.0, miles - LOCAL_RADIUS_MILES)
    fee = LOCAL_TRAVEL_FEE + (extra_miles * EXTRA_MILE_RATE)
    return round_money(fee), round(extra_miles, 1)


def make_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        textColor=colors.HexColor(DARK_SAGE),
        alignment=TA_CENTER,
        fontSize=21,
        leading=25,
    )
    center_style = ParagraphStyle(
        "Center",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
    )
    right_style = ParagraphStyle(
        "Right",
        parent=styles["BodyText"],
        alignment=TA_RIGHT,
    )
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#666666"))

    story = [
        Paragraph(BUSINESS_NAME, title_style),
        Paragraph(f"Mobile Notary Services<br/>{PHONE} • {EMAIL}", center_style),
        Spacer(1, 14),
        Table(
            [
                [Paragraph("SERVICE QUOTE", styles["Heading2"]), Paragraph(f"<b>Quote:</b> {data['quote_number']}<br/><b>Date:</b> {data['quote_date']}", right_style)],
            ],
            colWidths=[3.6 * inch, 3.0 * inch],
        ),
        Spacer(1, 10),
        Table(
            [
                ["Prepared for", data["customer_name"]],
                ["Phone", data["customer_phone"] or "Not provided"],
                ["Email", data["customer_email"] or "Not provided"],
                ["Appointment", data["appointment"]],
                ["Service location", data["destination"]],
                ["One way driving distance", f"{data['miles']:.1f} miles"],
            ],
            colWidths=[1.75 * inch, 4.85 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEE4")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(DARK_SAGE)),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D5D5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 16),
    ]

    rows = [["Description", "Amount"]]
    for label, amount in data["line_items"]:
        rows.append([label, currency(amount)])
    rows.extend(
        [
            ["Subtotal", currency(data["subtotal"])],
            [f"Sales tax ({data['tax_rate']:.3f}%)", currency(data["tax"])],
            ["TOTAL AGREED PRICE", currency(data["total"])],
        ]
    )
    charge_table = Table(rows, colWidths=[5.2 * inch, 1.4 * inch])
    charge_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_SAGE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D5D5")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2E8D2")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([charge_table, Spacer(1, 15)])

    payment_rows = [
        ["25% deposit required before services", currency(data["deposit"])],
        ["Deposit status", "PAID" if data["deposit_paid"] else "DUE"],
        ["Remaining balance due after signing", currency(data["remaining"])],
    ]
    payment_table = Table(payment_rows, colWidths=[5.2 * inch, 1.4 * inch])
    payment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8EEE4")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(SAGE)),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([payment_table, Spacer(1, 15)])

    if data["notes"]:
        story.extend([Paragraph("Appointment Notes", styles["Heading3"]), Paragraph(data["notes"], body), Spacer(1, 12)])

    acceptance = (
        "By accepting this quote, the customer agrees to the services and charges shown above. "
        "The 25% deposit is required before services are rendered. The remaining balance is due "
        "when the signing is complete. Changes to the location, appointment time, document count, "
        "or requested services may require a revised quote."
    )
    story.extend(
        [
            Paragraph("Customer Agreement", styles["Heading3"]),
            Paragraph(acceptance, body),
            Spacer(1, 12),
            Paragraph(f"<b>Accepted by:</b> {data['accepted_by'] or '________________________________'}", body),
            Paragraph(f"<b>Acceptance date:</b> {data['accepted_date'] if data['accepted_by'] else '________________'}", body),
            Spacer(1, 12),
            Paragraph(
                "Georgia notarial fees are listed separately where applicable. Travel, mobile, convenience, and after-hours charges are separate service fees disclosed before the appointment.",
                small,
            ),
            Paragraph(f"{LEGAL_NAME} doing business as {BUSINESS_NAME}", small),
        ]
    )

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


if "route" not in st.session_state:
    st.session_state.route = None
if "quote_number" not in st.session_state:
    st.session_state.quote_number = f"TSA-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"

st.markdown(
    f"""
    <div class="title-card">
        <h1 style="margin-bottom:.25rem;">The Signature Authority</h1>
        <p style="margin:0;color:{SAGE};">Mobile Notary Quote & Invoice Generator</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("quote_form"):
    st.subheader("Customer and appointment")
    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input("Customer name *")
        customer_phone = st.text_input("Customer phone")
        customer_email = st.text_input("Customer email")
    with col2:
        appointment_date = st.date_input("Appointment date", value=date.today())
        appointment_time = st.time_input("Appointment time")
        destination = st.text_input("Service address *", placeholder="Street, city, state and ZIP")

    st.subheader("Services")
    service = st.selectbox("Service needed", list(SERVICE_PRICES.keys()))
    col3, col4 = st.columns(2)
    with col3:
        notarial_acts = st.number_input("Number of notarial acts", min_value=0, step=1, value=1)
    with col4:
        after_hours = st.checkbox("Add after-hours fee (+$20)")

    custom_description = st.text_input("Optional additional service description")
    custom_amount = st.number_input("Optional additional charge", min_value=0.0, step=1.0, format="%.2f")

    st.subheader("Invoice settings")
    tax_rate = st.number_input(
        "Sales tax rate",
        min_value=0.0,
        max_value=20.0,
        value=0.0,
        step=0.001,
        format="%.3f",
        help="This defaults to 0%. Only change it after confirming that tax applies.",
    )
    notes = st.text_area("Appointment notes")
    calculate = st.form_submit_button("Calculate Quote")

if calculate:
    if not customer_name.strip() or not destination.strip():
        st.error("Enter the customer name and complete service address.")
    else:
        try:
            with st.spinner("Calculating the one way driving distance..."):
                miles, duration = calculate_one_way_distance(destination.strip())
            st.session_state.route = {
                "miles": miles,
                "duration": duration,
                "customer_name": customer_name.strip(),
                "customer_phone": customer_phone.strip(),
                "customer_email": customer_email.strip(),
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "destination": destination.strip(),
                "service": service,
                "notarial_acts": int(notarial_acts),
                "after_hours": after_hours,
                "custom_description": custom_description.strip(),
                "custom_amount": float(custom_amount),
                "tax_rate": float(tax_rate),
                "notes": notes.strip(),
            }
        except (requests.RequestException, ValueError) as exc:
            st.error(str(exc))

if st.session_state.route:
    data = st.session_state.route
    travel_fee, extra_miles = travel_fee_for(data["miles"])
    service_fee = SERVICE_PRICES[data["service"]]
    acts_fee = round_money(data["notarial_acts"] * NOTARIAL_ACT_FEE)

    line_items = [(data["service"], service_fee)]
    if extra_miles > 0:
        line_items.append((f"Local travel fee, first {LOCAL_RADIUS_MILES:.0f} miles", LOCAL_TRAVEL_FEE))
        line_items.append((f"{extra_miles:.1f} additional miles at {currency(EXTRA_MILE_RATE)} per mile", round_money(extra_miles * EXTRA_MILE_RATE)))
    else:
        line_items.append((f"Local travel fee, {data['miles']:.1f} one way miles", travel_fee))

    if data["notarial_acts"] > 0:
        line_items.append((f"{data['notarial_acts']} notarial act(s) at {currency(NOTARIAL_ACT_FEE)} each", acts_fee))
    if data["after_hours"]:
        line_items.append(("After-hours appointment surcharge", AFTER_HOURS_FEE))
    if data["custom_amount"] > 0:
        line_items.append((data["custom_description"] or "Additional service", round_money(data["custom_amount"])))

    subtotal = round_money(sum(amount for _, amount in line_items))
    tax = round_money(subtotal * data["tax_rate"] / 100)
    total = round_money(subtotal + tax)
    deposit = round_money(total * DEPOSIT_RATE)
    remaining = round_money(total - deposit)

    st.divider()
    st.header("Quote Preview")
    st.success(f"One way route: {data['miles']:.1f} miles • approximately {data['duration']}")

    for label, amount in line_items:
        st.markdown(f'<div class="price-box"><b>{label}</b><span style="float:right">{currency(amount)}</span></div>', unsafe_allow_html=True)

    st.write(f"**Subtotal:** {currency(subtotal)}")
    st.write(f"**Sales tax:** {currency(tax)}")
    st.markdown(f"### Total agreed price: {currency(total)}")

    deposit_paid = st.checkbox("Mark the 25% deposit as paid")
    accepted_by = st.text_input("Customer acceptance name", placeholder="Type the customer's name after they agree")
    accepted = st.checkbox("Customer agrees to the services, price, deposit, and remaining balance shown")

    due_now = 0.0 if deposit_paid else deposit
    st.info(
        f"Deposit required before services: {currency(deposit)}\n\n"
        f"Amount due now: {currency(due_now)}\n\n"
        f"Remaining due after signing: {currency(remaining)}"
    )

    pdf_data = {
        **data,
        "quote_number": st.session_state.quote_number,
        "quote_date": date.today().strftime("%B %d, %Y"),
        "appointment": f"{data['appointment_date'].strftime('%B %d, %Y')} at {data['appointment_time'].strftime('%I:%M %p')}",
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "deposit": deposit,
        "deposit_paid": deposit_paid,
        "remaining": remaining,
        "accepted_by": accepted_by.strip() if accepted else "",
        "accepted_date": date.today().strftime("%B %d, %Y"),
    }
    pdf = make_pdf(pdf_data)

    safe_name = "_".join(data["customer_name"].split())
    st.download_button(
        "Download Customer PDF Quote",
        data=pdf,
        file_name=f"{st.session_state.quote_number}_{safe_name}.pdf",
        mime="application/pdf",
    )

    if st.button("Start a New Quote"):
        st.session_state.route = None
        st.session_state.quote_number = f"TSA-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"
        st.rerun()

st.caption(
    "Travel distance is calculated one way from the private starting address saved in the app settings. "
    "The starting address is never printed on the customer quote."
)
