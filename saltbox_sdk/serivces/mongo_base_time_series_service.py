from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_time_series_base import TimeSeriesRepository
from saltbox_sdk.db.mongo.schemas_base import (
    CursoredTimeseriesResponse,
    IDMixin,
    MongoQuery,
    SortOrder,
    TimeseriesCursor,
)
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService


class MongoTimeseriesBaseService[
    Repository: TimeSeriesRepository,
    ModelType: IDMixin,
    CreateSchema: BaseModel,
](MongoBaseService[Repository, ModelType, CreateSchema, BaseModel]):
    async def get_list_in_range_paginated(
        self,
        *,
        query: MongoQuery,
        limit: int = 50,
        sort: dict[str, SortOrder] | None = None,
        after: TimeseriesCursor | None = None,
        before: TimeseriesCursor | None = None,
        session: MongoAsyncClientSession | None = None,
    ) -> CursoredTimeseriesResponse[ModelType]:
        time_f = self.repo.Meta.timeseries['timeField']
        going_backward = False

        base_sort = sort or {time_f: SortOrder.DESC, '_id': SortOrder.DESC}
        time_ascending = base_sort.get(time_f, SortOrder.ASC) == SortOrder.ASC
        id_ascending = base_sort.get('_id', SortOrder.ASC) == SortOrder.ASC

        query_parts: list[dict] = []
        if query:
            query_parts.append(query)

        if after is not None:
            time_op = '$gt' if time_ascending else '$lt'
            id_op = '$gt' if id_ascending else '$lt'
            query_parts.append(
                {
                    '$or': [
                        {time_f: {time_op: after.time}},
                        {time_f: after.time, '_id': {id_op: after.id}},
                    ]
                }
            )
        elif before is not None:
            going_backward = True
            time_op = '$lt' if time_ascending else '$gt'
            id_op = '$lt' if id_ascending else '$gt'
            query_parts.append(
                {
                    '$or': [
                        {time_f: {time_op: before.time}},
                        {time_f: before.time, '_id': {id_op: before.id}},
                    ]
                }
            )

        result_query: MongoQuery = {'$and': query_parts} if query_parts else {}

        fetch_sort = dict(base_sort)
        if going_backward:
            fetch_sort = {k: SortOrder(-v.value) for k, v in fetch_sort.items()}

        data = await self.get_list(
            query=result_query,
            limit=limit + 1,
            skip=0,
            sort=fetch_sort,
            session=session,
        )
        has_more = len(data) > limit
        if has_more:
            data = data[:-1]

        if going_backward:
            data.reverse()

        if not data:
            return CursoredTimeseriesResponse(data=[])

        first_item = data[0]
        last_item = data[-1]

        next_cursor = None
        previous_cursor = None

        if has_more or going_backward:
            next_cursor = TimeseriesCursor(time=getattr(last_item, time_f), id=last_item.id)

        if (after is not None and data) or (going_backward and has_more):
            previous_cursor = TimeseriesCursor(time=getattr(first_item, time_f), id=first_item.id)

        return CursoredTimeseriesResponse(
            data=data,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
        )
