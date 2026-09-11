# pygdo-payment-credits
Credits Payment Module for pygdo. Introduces credit user setting and allows purchasing and spending credits.

`payment_credits.order_credits.html` lets an authenticated user choose credits,
review the fixed purchase price, and select a payment processor. The account
sidebar links here and shows the current balance.

Like PHPGDO, `paycreds_min_purchase` defaults to EUR 5.00 and `paycreds_rate`
to EUR 0.01 per credit: the default minimum is 500 credits. Rates are calculated
with Decimal and rounded to cents. Limits are defined on the configuration GDTs.

The credits increment is an atomic database update committed together with the
order's paid marker. Opening checkout or returning without a confirmed capture
does not grant credits. Install `payment_paypal` and configure sandbox credentials
to exercise the checkout. The payment transaction requires InnoDB.

Tests (separate `pygdo_test` database):

```sh
.venv/bin/python gdoadm.py -u install payment_credits,payment_paypal
.venv/bin/python -m unittest gdo.payment_credits.test.test_order_credits -v
```
