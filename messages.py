from collections import defaultdict
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum, auto

from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import texts as t
from context import Context


class States(Enum):
    start = auto()
    entered = auto()
    not_confirmed = auto()
    confirmed = auto()
    validation_error = auto()


@dataclass
class MessageBase(ABC):
    bot_message: Message = None
    user_message: Message = None
    state: States = States.start

    @abstractmethod
    def get_text(self, ctx: Context):
        pass

    @abstractmethod
    def get_markup(self, ctx: Context):
        pass

    async def edit(self, ctx: Context):
        await self.bot_message.edit_text(
            self.get_text(ctx),
            reply_markup=self.get_markup(ctx)
        )

    async def answer(self, message: Message, ctx: Context):
        self.user_message = message
        self.bot_message = await message.answer(
            self.get_text(ctx),
            reply_markup=self.get_markup(ctx)
        )


class ListMessage(MessageBase, ABC):
    def get_markup(self, ctx: Context):
        if self.state in (States.start, States.entered, States.validation_error):
            return InlineKeyboardBuilder() \
                .button(text=t.END_OF_LIST_TEXT, callback_data=t.END_OF_LIST) \
                .as_markup()

        elif self.state == States.not_confirmed:
            return InlineKeyboardBuilder() \
                .button(text=t.ADD_MORE_TEXT, callback_data=t.ADD_MORE) \
                .as_markup()

        else:
            return InlineKeyboardBuilder().as_markup()


@dataclass
class NameMessage(MessageBase):
    def get_text(self, ctx: Context):
        if self.state == States.start:
            text = t.REPLY_ENTER_NAME
        else:
            text = ctx.name or t.NO_NAME

        return text

    def get_markup(self, ctx: Context):
        return None


@dataclass
class PeopleMessage(ListMessage):
    def get_text(self, ctx: Context):
        if self.state == States.start:
            text = t.REPLY_ENTER_PEOPLE
        else:
            text = t.REPLY_HERE_ARE_PEOPLE
        text += "\n"

        if ctx.people:
            text += "\n" + "\n".join(ctx.people) + "\n"

        text += "\n"
        if self.state == States.start:
            text += t.REPLY_CLICK_BELOW_TO_FINISH
        elif self.state == States.not_confirmed:
            text += t.REPLY_CLICK_BELOW_TO_EDIT

        return text


@dataclass
class PricesMessage(ListMessage):
    def get_text(self, ctx: Context):
        if self.state == States.start:
            text = t.REPLY_TYPE_A_PRICE
        else:
            text = t.REPLY_HERE_ARE_PRICES
        text += "\n"

        if ctx.prices:
            text += "\n"
            text += "\n".join(
                f"{', '.join(p.people)}: {p.value:.2f}" for p in ctx.prices
            )
            text += "\n"

        text += "\n"
        if self.state == States.start:
            text += t.REPLY_CLICK_BELOW_TO_FINISH
        elif self.state == States.validation_error:
            text += t.REPLY_NOT_A_NUMBER

        return text


@dataclass
class SelectPersonMessage(MessageBase):
    is_split: bool = False

    def get_text(self, ctx: Context):
        if self.state == States.validation_error:
            return t.REPLY_PERSON_NOT_IN_LIST

        if self.is_split:
            text = ", ".join(ctx.last_price().people)
            text += "\n"
            return text + t.REPLY_SELECT_PERSON

        return t.REPLY_SELECT_PEOPLE

    def get_markup(self, ctx: Context):

        if self.is_split:
            split_people = ctx.last_price().people
            kb = [
                [KeyboardButton(text=p) for p in ctx.people if p not in split_people],
                [KeyboardButton(text=t.END_OF_LIST_TEXT)],
            ]
        else:
            kb = [
                [KeyboardButton(text=p) for p in ctx.people],
                [KeyboardButton(text=t.SPLIT)],
                [KeyboardButton(text=t.EDIT_PRICE)]
            ]

        return ReplyKeyboardMarkup(
            keyboard=kb,
            resize_keyboard=True,
        )


class ServiceRateMessage(MessageBase):
    def get_text(self, ctx: Context):
        return t.REPLY_SELECT_SERVICE_RATE

    def get_markup(self, ctx: Context):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"{p}%") for p in [5, 10, 15, 20, 30]],
                [KeyboardButton(text=t.NO_SERVICE)]
            ],
            resize_keyboard=True,
        )


class TotalMessage(MessageBase):
    def get_text(self, ctx: Context):
        text = f"{ctx.name if ctx.name is not None else t.TOTAL_WITHOUT_NAME}:\n\n"

        totals = defaultdict(lambda: 0)
        for price in ctx.prices:
            for p in price.people:
                totals[p] += price.price_per_person()

        text += "\n".join(f"{name}: {total * (1 + ctx.service):.2f}" for name, total in totals.items())
        text += f"\n\n{t.TOTAL}: {sum(totals.values()) * (1 + ctx.service):.2f} ({ctx.service * 100}% {t.SERVICE})"
        return text

    def get_markup(self, ctx: Context):
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=t.SAVE),
                    KeyboardButton(text=t.DONT_SAVE),
                ],
            ],
            resize_keyboard=True,
        )