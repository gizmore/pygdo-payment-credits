from gdo.base.Application import Application
from gdo.base.GDO_Module import GDO_Module
from gdo.base.GDT import GDT
from gdo.base.Util import msg
from gdo.core.GDO_User import GDO_User
from gdo.core.GDT_UInt import GDT_UInt
from gdo.payment_credits.GDT_Credits import GDT_Credits
from gdo.ui.GDT_Link import GDT_Link

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from gdo.payment.GDT_Money import GDT_Money
from gdo.core.GDT_Decimal import GDT_Decimal

if TYPE_CHECKING:
    from gdo.ui.GDT_Page import GDT_Page


class module_payment_credits(GDO_Module):

    def gdo_classes(self):
        from gdo.payment_credits.GDO_CreditsOrder import GDO_CreditsOrder
        return [GDO_CreditsOrder]

    def credits_price(self, credits):
        rate = Decimal(str(self.get_config_val('paycreds_rate')))
        return (Decimal(credits) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def minimum_credits(self):
        rate = Decimal(str(self.get_config_val('paycreds_rate')))
        price = Decimal(str(self.get_config_val('paycreds_min_purchase')))
        return int((price / rate).to_integral_value(rounding=ROUND_CEILING))

    def gdo_dependencies(self) -> list:
        return [
            'payment',
        ]

    def gdo_module_config(self) -> list[GDT]:
        return [
            GDT_UInt('welcome_credits').initial('0'),
            GDT_Money('paycreds_min_purchase').min(0.01).max(1000000).not_null().initial('5.00'),
            GDT_Decimal('paycreds_rate').digits(6, 4).min(0.0001).max(999999).not_null().initial('0.01'),
        ]

    def cfg_welcome_credits(self) -> int:
        return self.get_config_value('welcome_credits')

    def gdo_user_config(self) -> list[GDT]:
        return [
            GDT_Credits('credits').initial('0'),
        ]

    def gdo_subscribe_events(self):
        Application.EVENTS.subscribe('user_created', self.on_user_created)

    async def on_user_created(self, user: GDO_User):
        if welcome_credits := self.cfg_welcome_credits():
            user.increase_setting('credits', welcome_credits)
            msg('msg_welcome_credits', (str(welcome_credits),))

    def gdo_init_sidebar(self, page: 'GDT_Page'):
        user = GDO_User.current()
        if user.is_user():
            credits = user.get_setting_value('credits')
            page._right_bar.add_field(
                GDT_Link('credits').href(self.href('order_credits')).text('link_credits', (credits,)).icon('credits')
            )
