from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from src.constant.app_constant import APP_PREFIX
from src.controller.dependency import get_current_client, get_notification_service
from src.dto.filter import FilterParams
from src.dto.notification_dto import NotificationOut, NotificationSummary
from src.dto.response import paginated_response, success_response
from src.model.client import Client
from src.security.rate_limit import limiter
from src.service.notification_service import NotificationService


notification_route = APIRouter(prefix=f"{APP_PREFIX}/notification", tags=["notifications"])


@notification_route.get("/")
@limiter.limit("30/minute")
def get_all(
    request: Request,
    filter: Annotated[FilterParams, Query()],
    client: Client = Depends(get_current_client),
    notification_service: NotificationService = Depends(get_notification_service),
):
    notifications, total = notification_service.get_all(client.id, filter.limit, filter.offset)
    data = [NotificationOut.model_validate(notification) for notification in notifications]
    return paginated_response(data=data, total=total, limit=filter.limit, offset=filter.offset)


@notification_route.get("/unread-count")
@limiter.limit("30/minute")
def get_unread_count(
    request: Request,
    client: Client = Depends(get_current_client),
    notification_service: NotificationService = Depends(get_notification_service),
):
    return success_response(
        data=NotificationSummary(unread_count=notification_service.count_unread(client.id))
    )


@notification_route.patch("/read-all")
@limiter.limit("30/minute")
def mark_all_as_read(
    request: Request,
    client: Client = Depends(get_current_client),
    notification_service: NotificationService = Depends(get_notification_service),
):
    updated = notification_service.mark_all_as_read(client.id)
    return success_response(data={"updated": updated})


@notification_route.patch("/{id}/read")
@limiter.limit("30/minute")
def mark_as_read(
    request: Request,
    id: str,
    client: Client = Depends(get_current_client),
    notification_service: NotificationService = Depends(get_notification_service),
):
    notification = notification_service.mark_as_read(id, client.id)
    return success_response(data=NotificationOut.model_validate(notification))
