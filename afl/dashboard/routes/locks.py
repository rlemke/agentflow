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

"""Lock visibility dashboard routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from ..dependencies import get_store

router = APIRouter(prefix="/locks")


def _current_time_ms() -> int:
    return int(time.time() * 1000)


@router.get("")
def lock_list(request: Request, store=Depends(get_store)):
    """List all locks with expired annotation."""
    locks = store.get_all_locks()
    now = _current_time_ms()
    return request.app.state.templates.TemplateResponse(
        request,
        "locks/list.html",
        {"locks": locks, "now": now},
    )


@router.get("/{lock_key:path}")
def lock_detail(lock_key: str, request: Request, store=Depends(get_store)):
    """Show lock detail."""
    # get_all_locks returns all (including expired); find by key
    locks = store.get_all_locks()
    lock = None
    for l in locks:
        if l.key == lock_key:
            lock = l
            break
    now = _current_time_ms()
    return request.app.state.templates.TemplateResponse(
        request,
        "locks/detail.html",
        {"lock": lock, "now": now},
    )


@router.post("/{lock_key:path}/release")
def release_lock(lock_key: str, store=Depends(get_store)):
    """Release a lock and redirect to list."""
    store.release_lock(lock_key)
    return RedirectResponse(url="/locks", status_code=303)
