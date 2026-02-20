import os
import zipfile
from xml.sax.saxutils import escape


OUTPUT_PATH = "Abils-Mall-Project-Manual.docx"


def para(text: str) -> str:
    return (
        "<w:p><w:r><w:t xml:space=\"preserve\">"
        + escape(text)
        + "</w:t></w:r></w:p>"
    )


title = "Abils Mall - Project Manual"
sections = [
    "1. Project Overview",
    "Abils Mall is a multi-vendor e-commerce platform built with Flask. It supports three role-based portals: Admin, Manager, and Buyer.",
    "The system handles product listing, cart and checkout, OTP-based verification, wallet/referral logic, payout control, and payment integrations.",
    "",
    "2. Main Roles and Permissions",
    "Admin: Creates companies and managers, reviews activities, manages users/orders/payouts/referrals/bank transfers, approves manager account requests, and monitors analytics.",
    "Manager: Manages products, submits reports, handles buyer approvals and discounts, and tracks company-level activities.",
    "Buyer: Registers and verifies account, browses products, places orders, manages profile, requests discounts, tracks activities, and can request manager upgrade.",
    "",
    "3. Core Architecture",
    "Backend: Python Flask with Blueprint modules (auth.py, admin.py, manager.py, shop.py, payments.py).",
    "Database: SQLAlchemy models with PostgreSQL in production (Render) and SQLite support for local development.",
    "Templates/UI: Jinja2 templates with centralized layout and responsive CSS.",
    "Authentication: Flask-Login session-based auth with role-based route checks.",
    "",
    "4. Authentication and Verification Logic",
    "Registration creates a user with buyer role by default.",
    "OTP verification logic is used during account flows and security-sensitive changes.",
    "Login and profile actions are logged into activity tables for traceability.",
    "Password reset and change-password routes are available for account security.",
    "",
    "5. Buyer to Manager Request Logic",
    "Buyer submits a manager request with company name.",
    "Admin sees requests in Manager Requests table.",
    "Admin sets commission rate and approves/rejects.",
    "On approval: buyer role is changed to manager, company link is assigned, commission is stored, and user gets notification (email/SMS if configured).",
    "",
    "6. Product and Order Logic",
    "Managers add/update/delete products tied to a company.",
    "Buyers add products to cart and place orders.",
    "Order records include delivery and shipping fields for operational handling.",
    "Payments and transfer approvals update order/payment status and company balances.",
    "",
    "7. Referral and Wallet Logic",
    "Referral wallet tracks token balances and earned totals.",
    "Withdrawal requests are reviewed by admin.",
    "Related cleanup logic is applied when deleting users to avoid foreign key failures.",
    "",
    "8. Activity and Audit Logic",
    "ActivityLog and CompanyActivity are used for operational visibility.",
    "Admin activity view is restricted to manager-originated activity logic where configured.",
    "Unread activity counters are tracked via per-role last-seen session timestamps.",
    "",
    "9. UI/UX Logic",
    "Global sidebar navigation with role-aware links.",
    "Responsive layouts for admin, manager, and buyer dashboards.",
    "Mobile behavior includes toggle sidebar and compact table/button handling.",
    "Navbar includes global product search and theme toggle (moon/sun).",
    "",
    "10. Deployment Logic (Render)",
    "Web process runs with Gunicorn.",
    "Environment variables configure database, secrets, mail/SMS providers, payment keys, and upload behavior.",
    "PostgreSQL URL is consumed from DATABASE_URL.",
    "Production dependencies include psycopg2-binary for PostgreSQL driver support.",
    "",
    "11. Security and Repository Hygiene",
    "Sensitive files are excluded from git history and .gitignore is used to avoid leaking secrets/databases/cache files.",
    "Fallback avatar logic prevents broken image issues when uploaded files are missing.",
    "Delete-user logic now handles linked records and foreign key constraints safely.",
    "",
    "12. Recommended Operations",
    "Set all required environment variables before production launch.",
    "Use PostgreSQL for production and run schema updates before go-live.",
    "Keep admin credentials private and rotate secrets if exposure is suspected.",
    "Monitor logs for payment callbacks, email/SMS delivery, and database constraint warnings.",
]


document_xml = (
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
    "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
    "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
    "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
    "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
    "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
    "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
    "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
    "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
    "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
    "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
    "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
    "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
    "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
    "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
    "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" "
    "mc:Ignorable=\"w14 wp14\">"
    "<w:body>"
    + para(title)
    + "".join(para(s) for s in sections)
    + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
    "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
    "<w:cols w:space=\"708\"/><w:docGrid w:linePitch=\"360\"/></w:sectPr>"
    "</w:body></w:document>"
)

content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


def build_docx(path: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


if __name__ == "__main__":
    build_docx(OUTPUT_PATH)
    print(os.path.abspath(OUTPUT_PATH))
