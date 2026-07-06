import json

import anyio

from saltbox_sdk.event_bus.schemas import MinionExtraCategoriesSyncMessage, MinionExtraDataCategory
from saltbox_sdk.event_bus.utils import send_message


async def extra_categories_sync(sender: str, paths_to_fixtures: list[anyio.Path]) -> None:
    categories: list[MinionExtraDataCategory] = []

    for path_to_fixtures in paths_to_fixtures:
        async with await anyio.open_file(path_to_fixtures, 'rb') as f:
            raw_data = json.loads(await f.read())

            if isinstance(raw_data, dict):
                categories.append(MinionExtraDataCategory.model_validate(raw_data))
            elif isinstance(raw_data, list):
                for item in raw_data:
                    categories.append(MinionExtraDataCategory.model_validate(item))
            else:
                msg = 'Fixtures file must contains list of categories or dict with category'
                raise TypeError(msg)

    await send_message(
        message=MinionExtraCategoriesSyncMessage(
            sender=sender,
            target='core',
            categories=categories,
        ),
        queue='minions_extra_categories_sync',
    )
