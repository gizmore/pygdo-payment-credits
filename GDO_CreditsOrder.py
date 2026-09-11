from decimal import Decimal

from gdo.base.Application import Application
from gdo.base.GDO import GDO
from gdo.base.Trans import t
from gdo.core.GDT_AutoInc import GDT_AutoInc
from gdo.core.GDT_User import GDT_User
from gdo.core.GDO_UserSetting import GDO_UserSetting
from gdo.payment.GDT_Money import GDT_Money
from gdo.payment.WithPayment import WithPayment
from gdo.payment_credits.GDT_Credits import GDT_Credits


class GDO_CreditsOrder(GDO, WithPayment):

    def gdo_columns(self):
        return [GDT_AutoInc('co_id'), GDT_User('co_user').not_null(),
                GDT_Credits('co_credits').not_null(), GDT_Money('co_price').not_null()]

    def gdo_can_purchase(self, user):
        return user.is_user() and self.gdo_val('co_user') == user.get_id()

    def gdo_price(self, user):
        return Decimal(self.gdo_val('co_price'))

    def gdo_allow_credits(self, user):
        return False

    def gdo_payment_title(self):
        return t('msg_credits_purchase', (int(self.gdo_val('co_credits')),))

    async def gdo_purchased(self, user):
        if not self.gdo_can_purchase(user) or not Application.db().is_in_transaction():
            return False
        credits = int(self.gdo_val('co_credits'))
        if credits <= 0:
            return False
        # Serialize initial setting creation for concurrent purchases by this user.
        user.select().where(user.pk_where()).for_update().exec().fetch_assoc()
        setting = GDO_UserSetting.table().get_by_id(user.get_id(), 'credits')
        if setting is None:
            setting = GDO_UserSetting.blank({'uset_user': user.get_id(),
                                            'uset_key': 'credits', 'uset_val': '0'}).insert()
        setting.increase('uset_val', credits)
        return True
