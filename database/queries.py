import time

from sqlalchemy import select
from . import get_session, models


async def get_totals(user_id, seconds_from_now, limit) -> list[models.Total]:
    command = (
        select(models.Total)
        .where(models.Total.user == user_id)
        .where(models.Total.timestamp >= seconds_from_now)
        .limit(limit)
    )

    s = get_session()
    res = await s.execute(command)
    return res.scalars().all()


async def save_total(total_text, user_id):
    total = models.Total()
    total.user = str(user_id)
    total.value = total_text
    total.timestamp = time.time()

    s = get_session()
    s.add(total)
    await s.flush((total,))
    await s.commit()