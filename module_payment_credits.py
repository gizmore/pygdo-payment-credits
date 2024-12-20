from gdo.base.Application import Application
from gdo.base.GDO_Module import GDO_Module
from gdo.base.GDT import GDT
from gdo.base.Util import msg
from gdo.core.GDO_User import GDO_User
from gdo.core.GDT_UInt import GDT_UInt


class module_payment_credits(GDO_Module):

    def gdo_dependencies(self) -> list:
        return [
            'payment',
        ]

    def gdo_module_config(self) -> list[GDT]:
        return [
            GDT_UInt('welcome_credits').initial('0'),
        ]

    def cfg_welcome_credits(self) -> int:
        return self.get_config_value('welcome_credits')

    def gdo_user_config(self) -> list[GDT]:
        return [
            GDT_UInt('credits').initial('0'),
        ]

    async def gdo_subscribe_events(self):
        Application.EVENTS.subscribe('user_created', self.on_user_created)

    def on_user_created(self, user: GDO_User):
        if welcome_credits := self.cfg_welcome_credits():
            user.increase_setting('credits', welcome_credits)
            msg('msg_welcome_credits', [str(welcome_credits)])
