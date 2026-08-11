"""Reusable FastAPI dependencies and query helpers.

Currently houses the ``PaginationParams`` dependency used by every list
endpoint and the ``apply_sort`` helper used by the filtered CRUD functions.
"""

import math
from typing import Iterable, Optional, Type

from fastapi import Query
from sqlalchemy.orm import Query as SQLAQuery

from app.utils import APIError, VALIDATION_ERROR


# --- Pagination -------------------------------------------------------------


class PaginationParams:
    """Captures the standard skip/limit/sort query parameters.

    Pulled into a route as::

        pagination: PaginationParams = Depends()
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        sort_by: Optional[str] = Query(None),
        sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    ) -> None:
        self.skip = skip
        self.limit = limit
        self.sort_by = sort_by
        self.sort_order = sort_order

    def paginate(
        self,
        query: SQLAQuery,
        sortable_columns: Iterable[str],
    ) -> tuple[list, int, int, int, int]:
        """Apply this pagination instance to ``query`` and return
        ``(items, total, page, pages, per_page)``.
        """
        sortable = set(sortable_columns)

        if self.sort_by is not None and self.sort_by not in sortable:
            raise APIError(
                status_code=422,
                message=f"sort_by '{self.sort_by}' is not sortable for this resource",
                code=VALIDATION_ERROR,
                details={"sort_by": sorted(sortable)},
            )

        apply_sort(
            query,
            model=None,
            sort_by=self.sort_by,
            sort_order=self.sort_order,
            sortable=sortable,
        )

        total = query.count()
        items = query.offset(self.skip).limit(self.limit).all()

        page = (self.skip // self.limit) + 1 if self.limit else 1
        pages = math.ceil(total / self.limit) if self.limit and total else 1
        per_page = self.limit

        return items, total, page, pages, per_page

    def pagination_block(self, total: int, page: int, pages: int, per_page: int) -> dict:
        return {
            "total": total,
            "page": page,
            "pages": pages,
            "per_page": per_page,
            "skip": self.skip,
            "limit": self.limit,
        }


# --- Sorting helper ---------------------------------------------------------


def apply_sort(
    query: SQLAQuery,
    model: Optional[Type] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    sortable: Optional[Iterable[str]] = None,
) -> SQLAQuery:
    """Apply an ORDER BY clause to ``query``.

    ``sortable`` is the per-call whitelist. Raises 422 if ``sort_by`` is set
    and not in ``sortable``.
    """
    if sort_by is None:
        return query

    if sortable is not None and sort_by not in set(sortable):
        raise APIError(
            status_code=422,
            message=f"sort_by '{sort_by}' is not sortable for this resource",
            code=VALIDATION_ERROR,
            details={"sort_by": sorted(set(sortable))},
        )

    if model is not None and hasattr(model, sort_by):
        column = getattr(model, sort_by)
        if sort_order == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())

    return query
