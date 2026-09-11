from gdo.payment.MethodPayment import MethodPayment
from gdo.payment_credits.GDO_CreditsOrder import GDO_CreditsOrder
from gdo.payment_credits.GDT_Credits import GDT_Credits
from gdo.payment_credits.module_payment_credits import module_payment_credits


class order_credits(MethodPayment):

    def gdo_create_form(self, form):
        minimum = module_payment_credits.instance().minimum_credits()
        form.add_field(GDT_Credits('co_credits').min(minimum).max(100000000).not_null().initial(str(minimum)))
        super().gdo_create_form(form)

    def get_orderable(self):
        credits = self.param_value('co_credits')
        module = module_payment_credits.instance()
        if credits < module.minimum_credits():
            raise ValueError('Below minimum purchase')
        return GDO_CreditsOrder.blank({
            'co_user': self._env_user.get_id(), 'co_credits': str(credits),
            'co_price': str(module.credits_price(credits)),
        })
