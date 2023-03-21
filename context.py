from dataclasses import dataclass, field

from aiogram.fsm.context import FSMContext


@dataclass()
class Context:
    name: str = None
    people: list[str] = field(default_factory=list)
    prices: list['Price'] = field(default_factory=list)
    service: float = 0
    total_text: str = None
    name_message: 'NameMessage' = None
    people_message: 'PeopleMessage' = None
    prices_message: 'PricesMessage' = None
    select_person_message: 'SelectPersonMessage' = None
    service_rate_message: 'ServiceRateMessage' = None
    total_message: 'TotalMessage' = None

    def last_price(self):
        return self.prices[-1]

    @classmethod
    async def add_to_state(cls, state: FSMContext):
        ctx = cls()
        await state.update_data(context=ctx)
        return ctx

    @staticmethod
    async def from_state(state: FSMContext) -> 'Context':
        return (await state.get_data())['context']


@dataclass()
class Price:
    value: float
    people: list[str] = field(default_factory=list)

    def price_per_person(self):
        return self.value / len(self.people)


