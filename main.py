import asyncio
import logging
import time
from os import getenv
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
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

import database
import texts as t
from context import Context, Price
from messages import (
    States,
    NameMessage,
    PeopleMessage,
    PricesMessage,
    SelectPersonMessage,
    ServiceRateMessage,
    TotalMessage
)

router = Router()


class Form(StatesGroup):
    start = State()
    sum = State()
    person = State()
    price = State()
    price_person = State()
    price_split = State()
    service = State()
    save = State()


@router.message(Command('start'))
async def start(message: Message, state: FSMContext):
    await state.set_state(Form.start)

    ctx = await Context.add_to_state(state)

    ctx.name_message = NameMessage()
    await ctx.name_message.answer(message, ctx)


@router.message(Command('history'))
async def history(message: Message, state: FSMContext):
    last_week_totals = await database.get_totals(
        message.from_user.id,
        time.time() - 60 * 60 * 24 * 7,
        limit=10
    )

    for total in last_week_totals:
        await message.answer(
            total.value,
            reply_markup=ReplyKeyboardRemove()
        )

    await message.answer(
        t.REPLY_ENTER_MEAL,
    )


@router.message(Form.start)
async def name(message: Message, state: FSMContext):
    await state.set_state(Form.person)

    ctx = await Context.from_state(state)

    # apparently a messages replying to /start can't be edited,
    # so we remove the old message and send a new one that we can edit
    if message.text != t.CONTINUE_WITHOUT_NAME:
        ctx.name = message.text
    ctx.name_message.state = States.entered
    name_message_to_delete = ctx.name_message.bot_message
    await ctx.name_message.answer(message, ctx)

    ctx.people_message = PeopleMessage()
    await ctx.people_message.answer(message, ctx)

    await name_message_to_delete.delete()
    await message.delete()


@router.message(Form.person, F.text != t.END_OF_LIST)
async def person(message: Message, state: FSMContext):
    ctx = await Context.from_state(state)
    ctx.people.append(message.text.strip())

    ctx.people_message.state = States.entered
    await ctx.people_message.edit(ctx)

    await message.delete()


@router.callback_query(Form.person, F.data == t.END_OF_LIST)
async def person_end(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Form.price)

    ctx = await Context.from_state(state)
    ctx.people_message.state = States.not_confirmed

    ctx.prices_message = PricesMessage()
    await ctx.prices_message.answer(ctx.people_message.bot_message, ctx)
    await ctx.people_message.edit(ctx)


@router.callback_query(Form.price, F.data == t.ADD_MORE)
async def add_more_people(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Form.person)

    ctx = await Context.from_state(state)
    ctx.people_message.state = States.entered

    await ctx.prices_message.bot_message.delete()
    await ctx.people_message.edit(ctx)


@router.message(Form.price, F.text != t.ADD_MORE and F.text != t.END_OF_LIST)
async def enter_price(message: Message, state: FSMContext):
    ctx = await Context.from_state(state)

    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        ctx.prices_message.state = States.validation_error
        await ctx.prices_message.edit(ctx)
        return await message.delete()

    await state.set_state(Form.price_person)
    ctx.prices_message.state = States.entered
    ctx.prices.append(Price(price))

    ctx.select_person_message = SelectPersonMessage()
    await ctx.select_person_message.answer(message, ctx)

    await ctx.prices_message.edit(ctx)


@router.message(Form.price_person, F.text == t.EDIT_PRICE)
async def edit_price(message: Message, state: FSMContext):
    await state.set_state(Form.price)

    set_keyboard_message = await message.answer(
        t.REPLY_TYPE_CHANGED_PRICE,
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Form.price_person, F.text == t.SPLIT)
async def split_price_persons(message: Message, state: FSMContext):
    await state.set_state(Form.price_split)

    ctx = await Context.from_state(state)
    prev_select_person = ctx.select_person_message

    ctx.select_person_message = SelectPersonMessage(is_split=True)
    await ctx.select_person_message.answer(message, ctx)

    await prev_select_person.bot_message.delete()
    await prev_select_person.user_message.delete()
    await message.delete()


@router.message(Form.price_person)
async def select_price_person(message: Message, state: FSMContext):
    ctx = await Context.from_state(state)

    if message.text not in ctx.people:
        ctx.prices_message.state = States.validation_error
        await ctx.prices_message.edit(ctx)
        return await message.delete()

    ctx.last_price().people.append(message.text)
    await state.set_state(Form.price)

    await ctx.prices_message.edit(ctx)
    await ctx.select_person_message.bot_message.delete()
    await ctx.select_person_message.user_message.delete()
    await message.delete()


@router.message(Form.price_split, F.text == t.END_OF_LIST_TEXT)
async def split_persons_end(message: Message, state: FSMContext):
    await state.set_state(Form.price)

    ctx = await Context.from_state(state)
    await ctx.prices_message.edit(ctx)

    await message.delete()
    await ctx.select_person_message.bot_message.delete()


@router.message(Form.price_split, F.text)
async def select_split_person(message: Message, state: FSMContext):
    ctx = await Context.from_state(state)

    last_select_to_delete = ctx.select_person_message.bot_message
    ctx.select_person_message = SelectPersonMessage(is_split=True)

    if message.text in ctx.people:
        ctx.last_price().people.append(message.text)
    else:
        ctx.select_person_message.state = States.validation_error

    await ctx.select_person_message.answer(message, ctx)
    await last_select_to_delete.delete()
    await message.delete()


@router.callback_query(Form.price, F.data == t.END_OF_LIST)
async def price_end(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Form.service)

    ctx = await Context.from_state(state)
    ctx.service_rate_message = ServiceRateMessage()

    await ctx.service_rate_message.answer(callback_query.message, ctx)


@router.message(Form.service)
async def select_service(message: Message, state: FSMContext):
    ctx = await Context.from_state(state)

    try:
        service = float(message.text.replace("%", "")) / 100
        ctx.service = service
    except ValueError:
        pass  # service will be 0 if none or error

    await state.set_state(Form.save)

    ctx.total_message = TotalMessage()
    await ctx.total_message.answer(message, ctx)

    ctx.people_message.state = States.confirmed
    ctx.prices_message.state = States.confirmed

    await ctx.service_rate_message.bot_message.delete()
    await ctx.service_rate_message.user_message.delete()
    await ctx.people_message.edit(ctx)
    await ctx.prices_message.edit(ctx)


@router.message(Form.save)
async def save_response(message: Message, state: FSMContext):
    if message.text == t.DONT_SAVE:
        await state.clear()
        return await message.answer(
            t.REPLY_DID_NOT_SAVE,
            reply_markup=ReplyKeyboardRemove()
        )

    ctx = await Context.from_state(state)

    await database.save_total(ctx.total_text, message.from_user.id)

    await state.clear()
    await message.answer(
        t.REPLY_SAVED if message.text == t.SAVE else t.REPLY_SAVED_ANYWAY
    )


async def main():
    bot = Bot(token=getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)

    db_url = getenv("SQLITE_URL") or "sqlite+aiosqlite:///./bot.sqlite?check_same_thread=False"
    database.create_db_sync(db_url)

    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    asyncio.run(main())
