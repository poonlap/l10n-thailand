# Copyright 2020 Poonlap V.
# Licensed AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Thai Localization - PromptPay",
    "version": "13.0.1.0.0",
    "author": "Poonlap V.,Odoo Community Association (OCA)",
    "website": "https://github.com/poonlap",
    "license": "AGPL-3",
    "category": "Accounting / Payment",
    "summary": "Use PromptPay QR code with transfer acquirer.",
    "depends": ["payment", "payment_transfer", "website_sale"],
    "data": [
        "data/payment_icon_data.xml",
        "views/payment_transfer_acquirer_form.xml",
        "views/views.xml",
    ],
    "external_dependencies": {"python": ["promptpay"]},
    "installable": True,
    "application": False,
}
