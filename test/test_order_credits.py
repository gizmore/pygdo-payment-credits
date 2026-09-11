import uuid
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from gdo.base.Application import Application
from gdo.base.Query import Type
from gdo.core.GDO_User import GDO_User
from gdo.core.GDO_Server import GDO_Server
from gdo.core.GDO_UserSetting import GDO_UserSetting
from gdo.payment.GDO_Order import GDO_Order
from gdo.payment_credits.GDO_CreditsOrder import GDO_CreditsOrder
from gdo.payment_credits.module_payment_credits import module_payment_credits
from gdo.payment_credits.method.order_credits import order_credits
from gdo.payment.method.choose import choose
from gdo.payment_paypal.method.capture import capture
from gdo.payment_paypal.module_payment_paypal import module_payment_paypal
from gdo.payment_paypal.PayPalClient import PayPalClient


class CreditsOrderTest(unittest.IsolatedAsyncioTestCase):
    """Integration tests against the separate, installed pygdo_test database."""

    async def asyncSetUp(self):
        Application.IS_HTTP = False
        Application.IS_TEST = True
        Application.init(str(Path(__file__).resolve().parents[3]))
        Application.init_cli()
        self.assertEqual('pygdo_test', Application.config('db.name'))
        Application.LOADER.load_modules_db(True)
        Application.LOADER.init_modules(True, True)
        server = GDO_Server.table().select().first().exec().fetch_object().get_id()
        name = 'payment_test_' + uuid.uuid4().hex[:12]
        result = GDO_User.table().query().type(Type.INSERT).set_vals({
            'user_type': 'member', 'user_name': name,
            'user_displayname': name, 'user_server': server}).exec()
        self._uid = str(result.lastrowid)
        self._user = GDO_User.table().get_by_id(self._uid)
        self._user._authenticated = True

    async def asyncTearDown(self):
        db = Application.db()
        if db.is_in_transaction():
            db.rollback()
        for table, key in [(GDO_Order, 'order_user'), (GDO_UserSetting, 'uset_user'), (GDO_User, 'user_id')]:
            table.table().delete_by_vals({key: self._uid})

    def order(self):
        item = GDO_CreditsOrder.blank({'co_user': self._uid, 'co_credits': '500', 'co_price': '5.00'})
        return GDO_Order.create_for(item, self._user)

    def balance(self):
        setting = GDO_UserSetting.table().get_by_id(self._uid, 'credits')
        return int(setting.gdo_val('uset_val')) if setting else 0

    async def test_increase_ignores_stale_object_balance(self):
        setting = GDO_UserSetting.blank({'uset_user': self._uid, 'uset_key': 'credits', 'uset_val': '10'}).insert()
        stale = GDO_UserSetting.table().get_by_id(self._uid, 'credits')
        setting.increase('uset_val', 7)
        stale.increase('uset_val', 3)
        self.assertEqual(20, self.balance())
        self.assertNotIn('uset_val', stale._dirty)

    async def test_checkout_without_processor_renders_error(self):
        from gdo.payment.PaymentModule import PaymentModule
        from gdo.ui.GDT_Error import GDT_Error
        order = self.order()
        checkout = choose().env_user(self._user).env_server(self._user.get_server())
        checkout.input('order', order.gdo_val('order_token'))
        with patch.object(PaymentModule, 'available', return_value=[]):
            self.assertIsInstance(checkout.render_page(), GDT_Error)
            self.assertTrue(checkout.render_html())

    async def test_money_has_two_localized_decimal_places(self):
        from gdo.payment.GDT_Money import GDT_Money
        from gdo.base.Trans import Trans
        with Trans('de'):
            self.assertEqual('2,00 €', GDT_Money('price').val('2').render_txt())
            self.assertEqual('2,01 €', GDT_Money('price').val('2.005').render_txt())

    async def test_checkout_invalid_order_renders_error(self):
        from gdo.ui.GDT_Error import GDT_Error
        checkout = choose().env_user(self._user).env_server(self._user.get_server())
        checkout.input('order', 'unknown-order')
        self.assertIsInstance(checkout.render_page(), GDT_Error)
        self.assertTrue(checkout.render_html())

    async def test_credit_once_after_reloading_order(self):
        order = self.order()
        self.assertEqual(0, self.balance())
        self.assertTrue(await order.complete(uuid.uuid4().hex))
        self.assertEqual(500, self.balance())
        fresh = GDO_Order.for_user(order.gdo_val('order_token'), self._user)
        self.assertFalse(await fresh.complete('duplicate'))
        self.assertEqual(500, self.balance())

    async def test_failed_fulfilment_rolls_back_credit_and_paid_marker(self):
        order = self.order()
        original = GDO_CreditsOrder.gdo_purchased

        async def fail_after_credit(item, user):
            await original(item, user)
            raise RuntimeError('Simulated failure after credit update')

        with patch.object(GDO_CreditsOrder, 'gdo_purchased', fail_after_credit):
            with self.assertRaises(RuntimeError):
                await order.complete(uuid.uuid4().hex)
        self.assertEqual(0, self.balance())
        fresh = GDO_Order.for_user(order.gdo_val('order_token'), self._user)
        self.assertEqual('pending', fresh.gdo_val('order_status'))
        self.assertTrue(await fresh.complete(uuid.uuid4().hex))
        self.assertEqual(500, self.balance())

    async def test_foreign_user_cannot_access_order(self):
        order = self.order()
        with self.assertRaises(ValueError):
            GDO_Order.for_user(order.gdo_val('order_token'), GDO_User.ghost())

    async def test_snapshot_price_and_default_conversion(self):
        module = module_payment_credits.instance()
        self.assertEqual(500, module.minimum_credits())
        self.assertEqual('5.00', str(module.credits_price(500)))
        self.assertEqual('5.01', str(module.credits_price(501)))
        order = self.order()
        snapshot = order.get_item()
        self.assertEqual('500', snapshot.gdo_val('co_credits'))
        self.assertEqual('5.00', str(snapshot.gdo_price(self._user)))

    async def test_forms_to_paypal_capture(self):
        Application.init_web({'REQUEST_METHOD': 'POST', 'REQUEST_URI': '/payment_credits.order_credits.html',
                              'HTTP_HOST': 'localhost', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80',
                              'wsgi.url_scheme': 'http', 'REMOTE_ADDR': '127.0.0.1'})
        Application.STORAGE.user = self._user
        buy = order_credits().env_user(self._user).env_server(self._user.get_server()).input('co_credits', '500').input('submit', '1')
        redirect = await buy.execute()
        self.assertIn('payment.choose', redirect._href)
        order = GDO_Order.table().get_by('order_user', self._uid)
        token = order.gdo_val('order_token')
        client = Mock(spec=PayPalClient)
        client._sandbox = True
        client.create_order.return_value = {'id': 'ORDER123', 'status': 'CREATED', 'links': [
            {'rel': 'payer-action', 'href': 'https://www.sandbox.paypal.com/checkoutnow?token=ORDER123'}]}
        with patch.object(module_payment_paypal, 'is_configured', return_value=True), \
                patch.object(module_payment_paypal, 'client', return_value=client):
            checkout = choose().env_user(self._user).env_server(self._user.get_server()).input('order', token)
            form = checkout.render_page()
            html = form.render_html()
            self.assertIn('pay_payment_paypal', html)
            self.assertIn('<img', html)
            checkout = choose().env_user(self._user).env_server(self._user.get_server()).input('order', token).input('pay_payment_paypal', '1')
            redirect = await checkout.execute()
            self.assertIn('sandbox.paypal.com', redirect._href)
            self.assertEqual(0, self.balance())
            completed = {'id': 'ORDER123', 'intent': 'CAPTURE', 'status': 'COMPLETED', 'purchase_units': [{
                'custom_id': token, 'amount': {'currency_code': 'EUR', 'value': '5.00'},
                'payments': {'captures': [{'id': uuid.uuid4().hex, 'status': 'COMPLETED',
                                         'amount': {'currency_code': 'EUR', 'value': '5.00'}}]},
            }]}
            client.get_order.side_effect = [dict(completed, status='APPROVED'), completed]
            client.verify_order.side_effect = PayPalClient.verify_order
            returned = capture().env_user(self._user).env_server(self._user.get_server()).input('order', token).input('token', 'ORDER123')
            with patch('gdo.payment_paypal.method.capture.IPC.send') as ipc:
                await returned.execute()
                ipc.assert_called_once_with('base.ipc_uset', (self._uid, 'credits', '500'))
            self.assertEqual(500, self.balance())
            client.capture_order.assert_called_once_with('ORDER123', token)


if __name__ == '__main__':
    unittest.main()
