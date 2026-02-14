# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Event dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store

router = APIRouter(prefix="/events")


@router.get("")
def event_list(request: Request, state: str | None = None, store=Depends(get_store)):
    """List all events, optionally filtered by state."""
    if state:
        events = store.get_events_by_state(state)
    else:
        events = store.get_all_events()
    return request.app.state.templates.TemplateResponse(
        request,
        "events/list.html",
        {"events": events, "filter_state": state},
    )


@router.get("/{event_id}")
def event_detail(event_id: str, request: Request, store=Depends(get_store)):
    """Show event detail."""
    event = store.get_event(event_id)
    return request.app.state.templates.TemplateResponse(
        request,
        "events/detail.html",
        {"event": event},
    )
