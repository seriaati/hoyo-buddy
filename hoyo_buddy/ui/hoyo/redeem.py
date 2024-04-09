from ...bot.translator import LocaleStr
from ..components import Modal, TextInput


class GiftCodeModal(Modal):
    code_1 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=1)
    )
    code_2 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=2),
        required=False,
    )
    code_3 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=3),
        required=False,
    )
    code_4 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=4),
        required=False,
    )
    code_5 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=5),
        required=False,
    )
