"""Reflex UI exposing the research MCP workflows."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import reflex as rx

if not hasattr(rx, "wrap"):
    def _wrap(*children: rx.Component, **props: str) -> rx.Component:
        """Fallback implementation for reflex.wrap on older Reflex builds."""

        props.setdefault("flex_wrap", "wrap")
        return rx.flex(*children, **props)

    rx.wrap = _wrap  # type: ignore[attr-defined]

from frontend.services import mcp
from frontend.services.mcp import MCPClientError

ACCENT_LIGHT = "#6366F1"
ACCENT_DARK = "#7C3AED"
BACKGROUND_LIGHT = "#F5F7FA"
BACKGROUND_DARK = "#111827"
SUCCESS_ACCENT = "#FFB347"


class AppState(rx.State):
    """Global application state for the research console."""

    base_url: str = "http://127.0.0.1:8000"
    available_servers: List[Dict[str, str]] = [
        {"label": "General MCP", "url": "http://127.0.0.1:8000"},
        {"label": "Cupcake Demo", "url": "http://127.0.0.1:8001"},
        {"label": "Funder Evaluation", "url": "http://127.0.0.1:8002"},
    ]
    custom_base_url: str = base_url

    handshake: Dict[str, Any] | None = None
    handshake_loading: bool = False
    handshake_error: str = ""
    handshake_last_updated: str | None = None

    tool_inventory: List[Dict[str, str]] = []
    tool_inventory_loading: bool = False

    search_query: str = ""
    search_method: str = "simple"
    search_loading: bool = False
    search_error: str = ""

    records: List[Dict[str, Any]] = []
    selected_record_id: str | None = None

    max_query_length: int = 512
    max_identifier_length: int = 128
    max_packet_concurrency: int = 10

    evaluation_query: str = ""
    evaluation_loading: bool = False
    evaluation_error: str = ""
    evaluation_result: Dict[str, Any] | None = None

    activity_log: List[str] = []
    max_activity_entries: int = 25

    # --- derived helpers -------------------------------------------------
    @rx.var
    def handshake_name(self) -> str:
        if not self.handshake:
            return "Unknown server"
        return str(self.handshake.get("name") or "Research MCP").strip() or "Research MCP"

    @rx.var
    def handshake_instructions(self) -> str:
        if not self.handshake:
            return ""
        return str(self.handshake.get("instructions") or "").strip()

    @rx.var
    def handshake_tools(self) -> List[Dict[str, str]]:
        if not self.handshake:
            return []
        tools = self.handshake.get("tools")
        if isinstance(tools, list):
            cleaned: list[dict[str, str]] = []
            for tool in tools:
                if isinstance(tool, dict) and tool.get("name"):
                    cleaned.append({
                        "name": str(tool.get("name", "")),
                        "description": str(tool.get("description", "")),
                    })
            return cleaned
        return []

    @rx.var
    def handshake_last_updated_display(self) -> str:
        if not self.handshake_last_updated:
            return ""
        try:
            dt = datetime.fromisoformat(self.handshake_last_updated)
        except ValueError:
            return self.handshake_last_updated
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z") or dt.isoformat(timespec="seconds")

    @rx.var
    def server_options(self) -> List[Dict[str, str]]:
        return self.available_servers

    @rx.var
    def has_selected_record(self) -> bool:
        return self.selected_record is not None

    @rx.var
    def available_search_methods(self) -> List[str]:
        methods = {"simple"}
        handshake_meta = self.handshake or {}
        metadata = handshake_meta.get("meta") if isinstance(handshake_meta, dict) else None
        if isinstance(metadata, dict):
            raw_methods = metadata.get("search_methods")
            if isinstance(raw_methods, list):
                methods.update(str(item) for item in raw_methods if isinstance(item, str))
        return sorted(methods)

    @rx.var
    def has_records(self) -> bool:
        return bool(self.records)

    @rx.var
    def selected_record(self) -> Dict[str, Any] | None:
        if not self.selected_record_id:
            return None
        for record in self.records:
            if record.get("id") == self.selected_record_id:
                return record
        return None

    @rx.var
    def selected_record_metadata_items(self) -> List[Dict[str, str]]:
        record = self.selected_record
        if not record:
            return []
        items = record.get("metadata_items")
        if isinstance(items, list):
            return items
        return []

    @rx.var
    def has_selected_record_metadata(self) -> bool:
        return bool(self.selected_record_metadata_items)

    @rx.var
    def evaluation_resolved(self) -> List[Dict[str, str]]:
        if not self.evaluation_result:
            return []
        items = self.evaluation_result.get("resolved")
        if isinstance(items, list):
            return items
        return []

    @rx.var
    def evaluation_fallback(self) -> List[Dict[str, str]]:
        if not self.evaluation_result:
            return []
        items = self.evaluation_result.get("fallback")
        if isinstance(items, list):
            return items
        return []

    # --- lifecycle -------------------------------------------------------
    async def on_app_load(self) -> None:
        await self.refresh_handshake()
        await self.refresh_tool_inventory()

    def _append_activity(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        updated = self.activity_log + [entry]
        if len(updated) > self.max_activity_entries:
            updated = updated[-self.max_activity_entries :]
        self.activity_log = updated

    # --- server metadata -------------------------------------------------
    async def refresh_handshake(self) -> None:
        self.handshake_loading = True
        self.handshake_error = ""
        try:
            metadata = await mcp.fetch_handshake(self.base_url)
            self.handshake = metadata.to_dict()
            self.handshake_last_updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._append_activity(f"Connected to {metadata.name}")
        except Exception as exc:  # pragma: no cover - reactive feedback
            self.handshake_error = str(exc)
            self.handshake = None
        finally:
            self.handshake_loading = False

    async def refresh_tool_inventory(self) -> None:
        self.tool_inventory_loading = True
        try:
            tools = await mcp.list_tools(self.base_url)
            self.tool_inventory = [tool.__dict__ for tool in tools]
        except Exception as exc:  # pragma: no cover - diagnostics only
            self.tool_inventory = []
            self._append_activity(f"Tool inventory failed: {exc}")
        finally:
            self.tool_inventory_loading = False

    async def change_server(self, url: str) -> None:
        cleaned = url.strip()
        if not cleaned or cleaned == self.base_url:
            return
        self.base_url = cleaned
        self.custom_base_url = cleaned
        self.records = []
        self.selected_record_id = None
        self.search_error = ""
        self.evaluation_error = ""
        self.evaluation_result = None
        await self.refresh_handshake()
        await self.refresh_tool_inventory()

    def set_custom_base_url(self, value: str) -> None:
        self.custom_base_url = value

    async def apply_custom_base_url(self) -> None:
        await self.change_server(self.custom_base_url)

    # --- search workflow -------------------------------------------------
    def set_search_query(self, value: str) -> None:
        self.search_query = value

    def set_search_method(self, method: str) -> None:
        self.search_method = method

    async def run_search(self) -> None:
        query = self.search_query.strip()
        if not query:
            self.search_error = "Enter a search query before submitting."
            return
        if len(query) > self.max_query_length:
            self.search_error = f"Queries must be {self.max_query_length} characters or fewer."
            return
        self.search_loading = True
        self.search_error = ""
        try:
            ids = await mcp.search_ids(self.base_url, query, method=self.search_method)
            self._append_activity(f"Search for '{query}' returned {len(ids)} ids")
            resolved_records: list[dict[str, Any]] = []
            for record_id in ids:
                try:
                    record = await mcp.fetch_record(self.base_url, record_id)
                except MCPClientError as exc:
                    self._append_activity(f"Fetch {record_id} failed: {exc}")
                    continue
                metadata = record.get("metadata") if isinstance(record, dict) else {}
                metadata_items: list[dict[str, str]] = []
                if isinstance(metadata, dict):
                    for key, value in metadata.items():
                        metadata_items.append({"key": str(key), "value": str(value)})
                raw_json = json.dumps(record, indent=2, sort_keys=True)
                resolved_records.append(
                    {
                        "id": record.get("id", record_id),
                        "title": record.get("title") or "Untitled record",
                        "text": record.get("text", ""),
                        "metadata_items": metadata_items,
                        "raw_json": raw_json,
                    }
                )
            self.records = resolved_records
            self.selected_record_id = resolved_records[0]["id"] if resolved_records else None
            if not resolved_records:
                self._append_activity("Search completed with no matching records")
        except MCPClientError as exc:
            self.search_error = str(exc)
            self.records = []
            self.selected_record_id = None
        finally:
            self.search_loading = False

    async def select_record(self, record_id: str) -> None:
        self.selected_record_id = record_id

    # --- evaluation ------------------------------------------------------
    def set_evaluation_query(self, value: str) -> None:
        self.evaluation_query = value

    async def run_evaluation(self) -> None:
        query = self.evaluation_query.strip()
        if query and len(query) > self.max_query_length:
            self.evaluation_error = f"Queries must be {self.max_query_length} characters or fewer."
            return
        self.evaluation_loading = True
        self.evaluation_error = ""
        try:
            result = await mcp.evaluate_funder(self.base_url, query=query or None)
            resolved_items: list[dict[str, str]] = []
            fallback_items: list[dict[str, str]] = []
            for key, value in result.items():
                entry = {"key": str(key), "value": "" if value is None else str(value)}
                if value is None:
                    fallback_items.append(entry)
                else:
                    resolved_items.append(entry)
            assigned = len(resolved_items)
            self.evaluation_result = {
                "raw": result,
                "resolved": resolved_items,
                "fallback": fallback_items,
            }
            self._append_activity(
                f"Evaluation assigned {assigned} of {len(result)} variables"
            )
        except MCPClientError as exc:
            self.evaluation_error = str(exc)
            self.evaluation_result = None
        finally:
            self.evaluation_loading = False

    # --- activity --------------------------------------------------------
    def clear_activity(self) -> None:
        self.activity_log = []


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def shell_layout(*children: rx.Component) -> rx.Component:
    return rx.box(
        header(),
        rx.box(
            *children,
            max_width="1200px",
            width="100%",
            margin="0 auto",
            padding_x="2rem",
            padding_y="2.5rem",
        ),
        width="100%",
        min_height="100vh",
        background=rx.color_mode_cond(BACKGROUND_LIGHT, BACKGROUND_DARK),
    )


def header() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    "Research MCP Console",
                    font_family="Rubik",
                    font_size="1.75rem",
                    font_weight="600",
                ),
                rx.text(
                    "Search records, inspect payloads, and run funder evaluations.",
                    color=rx.color_mode_cond("#4B5563", "#D1D5DB"),
                    font_size="0.95rem",
                ),
                spacing="1",
                align_items="flex-start",
            ),
            server_selector(),
            justify="space-between",
            align_items="center",
            width="100%",
            padding_x="2rem",
            padding_y="1.25rem",
        ),
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 8px 30px rgba(15, 23, 42, 0.12)",
        width="100%",
    )


def server_selector() -> rx.Component:
    def option_button(option: Dict[str, str]) -> rx.Component:
        url = option.get("url", "")
        label = option.get("label", url)
        return rx.button(
            label,
            variant=rx.cond(AppState.base_url == url, "solid", "outline"),
            on_click=lambda url=url: AppState.change_server(url),
        )

    return rx.vstack(
        rx.text("Server", font_weight="600", font_size="0.85rem"),
        rx.wrap(
            rx.foreach(AppState.server_options, option_button),
            spacing="2",
        ),
        rx.input(
            value=AppState.custom_base_url,
            on_change=AppState.set_custom_base_url,
            on_blur=AppState.apply_custom_base_url,
            placeholder="Custom base URL",
            width="18rem",
        ),
        spacing="2",
        align_items="flex-end",
    )


def status_banner() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(AppState.handshake_name, size="5"),
                rx.badge(AppState.base_url, color_scheme="gray"),
                rx.cond(
                    AppState.handshake_last_updated_display != "",
                    rx.badge(
                        AppState.handshake_last_updated_display,
                        color_scheme="gray",
                        variant="soft",
                    ),
                ),
                spacing="3",
                align_items="center",
                wrap="wrap",
            ),
            rx.cond(
                AppState.handshake_instructions != "",
                rx.text(
                    AppState.handshake_instructions,
                    color=rx.color_mode_cond("#4B5563", "#CBD5F5"),
                    max_width="100%",
                ),
            ),
            rx.wrap(
                rx.foreach(
                    AppState.handshake_tools,
                    lambda tool: rx.badge(
                        tool["name"],
                        title=tool.get("description", ""),
                        color_scheme="indigo",
                        variant="soft",
                    ),
                ),
                spacing="2",
            ),
            spacing="3",
            align_items="flex-start",
        ),
        padding="1.75rem",
        border_radius="1.5rem",
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 20px 45px rgba(15, 23, 42, 0.1)",
        width="100%",
    )


def search_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.input(
                    placeholder="Search the corpus…",
                    value=AppState.search_query,
                    on_change=AppState.set_search_query,
                    width="100%",
                ),
                method_selector(),
                rx.button(
                    "Search",
                    on_click=AppState.run_search,
                    loading=AppState.search_loading,
                    disabled=AppState.search_loading,
                    background=ACCENT_LIGHT,
                    color="white",
                    _dark={"background": ACCENT_DARK},
                ),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                AppState.search_error != "",
                rx.text(AppState.search_error, color="#DC2626"),
            ),
            spacing="2",
        ),
        padding="1.5rem",
        border_radius="1.25rem",
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 10px 30px rgba(15, 23, 42, 0.08)",
        width="100%",
    )


def method_selector() -> rx.Component:
    return rx.wrap(
        rx.foreach(
            AppState.available_search_methods,
            lambda method: rx.button(
                method,
                size="2",
                variant=rx.cond(AppState.search_method == method, "solid", "outline"),
                on_click=lambda value=method: AppState.set_search_method(value),
            ),
        ),
        spacing="2",
    )


def results_section() -> rx.Component:
    def record_card(record: Dict[str, Any]) -> rx.Component:
        return rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text(
                        record.get("title", "Untitled record"),
                        font_weight="600",
                        font_size="1.1rem",
                    ),
                    rx.badge(str(record.get("id", "")), color_scheme="gray"),
                    justify="space-between",
                    align_items="center",
                    width="100%",
                ),
                rx.text(
                    record.get("text", ""),
                    color=rx.color_mode_cond("#4B5563", "#CBD5F5"),
                ),
                rx.wrap(
                    rx.foreach(
                        record.get("metadata_items", []),
                        lambda item: rx.box(
                            rx.text(f"{item['key']}: {item['value']}", font_size="0.8rem"),
                            padding_x="0.65rem",
                            padding_y="0.35rem",
                            border_radius="999px",
                            background=rx.color_mode_cond("#EEF2FF", "rgba(99, 102, 241, 0.12)"),
                            color=rx.color_mode_cond("#3730A3", "#C7D2FE"),
                        ),
                    ),
                    spacing="2",
                ),
                rx.button(
                    "View details",
                    variant="outline",
                    on_click=lambda id=record.get("id", ""): AppState.select_record(str(id)),
                    width="max-content",
                ),
                spacing="2",
                align_items="flex-start",
            ),
            padding="1.25rem",
            border_radius="1rem",
            background=rx.color_mode_cond("white", "#111827"),
            box_shadow="0 12px 30px rgba(15, 23, 42, 0.08)",
            width="100%",
        )

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Results", size="4"),
                rx.badge(
                    rx.cond(
                        AppState.has_records,
                        lambda: f"{len(AppState.records)} records",
                        lambda: "0 records",
                    ),
                    color_scheme="gray",
                    variant="soft",
                ),
                justify="space-between",
                align_items="center",
                width="100%",
            ),
            rx.cond(
                AppState.search_loading,
                rx.center(rx.spinner(size="sm"), height="6rem"),
                rx.cond(
                    AppState.has_records,
                    rx.grid(
                        rx.foreach(AppState.records, record_card),
                        columns=["1fr", "1fr"],
                        spacing="1.5rem",
                        width="100%",
                    ),
                    rx.box(
                        rx.text(
                            "No results yet. Run a search to see matching records.",
                            color=rx.color_mode_cond("#6B7280", "#9CA3AF"),
                        ),
                        padding="2rem",
                        text_align="center",
                        width="100%",
                    ),
                ),
            ),
            spacing="3",
        ),
        width="100%",
    )


def record_detail() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Record detail", size="4"),
            rx.cond(
                AppState.has_selected_record,
                record_detail_content,
                rx.text(
                    "Select a record to inspect its metadata and raw JSON.",
                    color=rx.color_mode_cond("#6B7280", "#9CA3AF"),
                ),
            ),
            spacing="3",
        ),
        padding="1.5rem",
        border_radius="1.25rem",
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 10px 30px rgba(15, 23, 42, 0.08)",
        width="100%",
    )


def record_detail_content() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                AppState.selected_record["title"],
                font_weight="600",
                font_size="1.25rem",
            ),
            rx.button(
                "Copy ID",
                variant="outline",
                on_click=rx.set_clipboard(AppState.selected_record["id"]),
            ),
            justify="space-between",
            align_items="center",
            width="100%",
        ),
        rx.text(AppState.selected_record.get("text", "")),
        rx.vstack(
            rx.heading("Metadata", size="3"),
            rx.cond(
                AppState.has_selected_record_metadata,
                rx.foreach(
                    AppState.selected_record_metadata_items,
                    lambda item: rx.hstack(
                        rx.text(item["key"], font_weight="600", width="30%"),
                        rx.text(item["value"], width="70%"),
                    ),
                ),
                rx.text("No metadata values available."),
            ),
            spacing="2",
            width="100%",
        ),
        rx.vstack(
            rx.heading("Raw JSON", size="3"),
            rx.code_block(AppState.selected_record["raw_json"], language="json"),
            spacing="1",
            width="100%",
        ),
        spacing="2",
    )


def evaluation_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Funder evaluation", size="4"),
                rx.badge(
                    f"Max concurrency {AppState.max_packet_concurrency}",
                    color_scheme="orange",
                    variant="soft",
                ),
                justify="space-between",
                align_items="center",
                width="100%",
            ),
            rx.text(
                "Run the evaluate tool to populate derived funder variables.",
                color=rx.color_mode_cond("#4B5563", "#CBD5F5"),
            ),
            rx.hstack(
                rx.input(
                    placeholder="Optional query filter",
                    value=AppState.evaluation_query,
                    on_change=AppState.set_evaluation_query,
                    width="100%",
                ),
                rx.button(
                    "Run evaluation",
                    on_click=AppState.run_evaluation,
                    loading=AppState.evaluation_loading,
                    disabled=AppState.evaluation_loading,
                    background=SUCCESS_ACCENT,
                    color="black",
                ),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                AppState.evaluation_error != "",
                rx.text(AppState.evaluation_error, color="#DC2626"),
            ),
            rx.cond(
                AppState.evaluation_loading,
                rx.center(rx.spinner(size="sm"), height="5rem"),
                evaluation_result_panel,
            ),
            spacing="3",
        ),
        padding="1.5rem",
        border_radius="1.25rem",
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 12px 30px rgba(15, 23, 42, 0.08)",
        width="100%",
    )


def evaluation_result_panel() -> rx.Component:
    return rx.cond(
        AppState.evaluation_result is None,
        rx.text(
            "No evaluation has been run yet.",
            color=rx.color_mode_cond("#6B7280", "#9CA3AF"),
        ),
        rx.hstack(
            rx.vstack(
                rx.heading("Resolved variables", size="3"),
                rx.cond(
                    AppState.evaluation_resolved,
                    rx.foreach(
                        AppState.evaluation_resolved,
                        lambda item: rx.box(
                            rx.text(f"{item['key']}: {item['value']}", font_size="0.9rem"),
                            padding="0.75rem",
                            border_radius="0.75rem",
                            background=rx.color_mode_cond("rgba(99,102,241,0.12)", "rgba(99,102,241,0.18)"),
                        ),
                    ),
                    rx.text("No variables resolved yet."),
                ),
                spacing="2",
                width="50%",
            ),
            rx.vstack(
                rx.heading("Fallback values", size="3"),
                rx.cond(
                    AppState.evaluation_fallback,
                    rx.foreach(
                        AppState.evaluation_fallback,
                        lambda item: rx.box(
                            rx.text(item["key"], font_size="0.9rem"),
                            padding="0.75rem",
                            border_radius="0.75rem",
                            border="1px solid rgba(148, 163, 184, 0.3)",
                        ),
                    ),
                    rx.text("No fallback entries applied."),
                ),
                spacing="2",
                width="50%",
            ),
            spacing="3",
            width="100%",
        ),
    )


def activity_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Activity & diagnostics", size="4"),
                rx.button("Clear", variant="ghost", on_click=AppState.clear_activity),
                justify="space-between",
                align_items="center",
                width="100%",
            ),
            rx.cond(
                AppState.activity_log,
                rx.vstack(
                    rx.foreach(
                        AppState.activity_log,
                        lambda entry: rx.box(
                            rx.text(entry, font_family="Inter", font_size="0.85rem"),
                            padding_y="0.35rem",
                        ),
                    ),
                    spacing="1",
                    max_height="12rem",
                    overflow="auto",
                    width="100%",
                ),
                rx.text(
                    "No recent activity – actions will appear here as you interact with the tools.",
                    color=rx.color_mode_cond("#6B7280", "#9CA3AF"),
                ),
            ),
            spacing="2",
        ),
        padding="1.5rem",
        border_radius="1.25rem",
        background=rx.color_mode_cond("white", "#1F2937"),
        box_shadow="0 8px 24px rgba(15, 23, 42, 0.08)",
        width="100%",
    )


def index() -> rx.Component:
    return shell_layout(
        rx.vstack(
            status_banner(),
            rx.box(height="1.5rem"),
            search_section(),
            rx.box(height="1.5rem"),
            results_section(),
            rx.box(height="1.5rem"),
            record_detail(),
            rx.box(height="1.5rem"),
            evaluation_section(),
            rx.box(height="1.5rem"),
            activity_section(),
            spacing="1",
            width="100%",
        )
    )


app = rx.App(
    theme=rx.theme(
        appearance="light",
        accent_color="indigo",
        radius="large",
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Rubik:wght@600;700&display=swap",
    ],
)
app.add_page(index, on_load=AppState.on_app_load, title="Research MCP Console")
